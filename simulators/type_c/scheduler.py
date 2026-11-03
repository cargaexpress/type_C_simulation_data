"""Autonomous background scheduler and batch file depositor for Type C carriers (Source F5).

Periodically generates synthetic tracking files with defect injection for all 3 carriers
and deposits them into MinIO / S3 Object Storage every 4 hours, enforcing automatic
retention cleanup to eliminate storage bloat and costs.
"""

import argparse
import json
import logging
import os
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from simulators.type_c.catalogs import CARRIERS_REGISTRY, get_carrier_config
from simulators.type_c.generator import TypeCSimulator, compute_file_sha256
from simulators.type_c.storage import S3StorageManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)
logger = logging.getLogger("type_c_scheduler")


def wait_for_storage(storage: S3StorageManager, max_retries: int = 30, delay: int = 2) -> None:
    """Block until MinIO/S3 endpoint is reachable."""
    logger.info("Checking connection to MinIO/S3 at %s...", storage.endpoint_url)
    for attempt in range(1, max_retries + 1):
        try:
            storage.s3_client.list_buckets()
            logger.info("Successfully connected to Object Storage on attempt %d.", attempt)
            return
        except Exception as exc:
            logger.warning("Attempt %d/%d: Storage not ready yet (%s). Retrying in %ds...", attempt, max_retries, exc, delay)
            time.sleep(delay)
    raise ConnectionError(f"Could not connect to Object Storage at {storage.endpoint_url} after {max_retries} attempts.")


# Shared latest state in memory for API endpoints
LATEST_STATE: dict[str, Any] = {
    "cycle_id": None,
    "last_updated": None,
    "carriers": {},
}


def run_batch_cycle(
    storage: S3StorageManager,
    rows_per_carrier: int = 100,
    error_rate: float = 0.10,
    seed: int = 42,
    retention_days: int = 3,
    local_export_dir: Path | None = None,
) -> dict[str, Any]:
    """Execute a single batch cycle: cleanup expired data, generate carrier files, and upload."""
    cycle_time = datetime.now(UTC)
    date_folder = cycle_time.strftime("%Y-%m-%d")
    timestamp_str = cycle_time.strftime("%Y%m%dT%H%M%SZ")
    cycle_id = f"cycle-{timestamp_str}"

    logger.info("==================================================")
    logger.info("Starting Type C Batch Cycle: %s", cycle_id)
    logger.info("Configuration: rows=%d, error_rate=%.2f, seed=%d, retention_days=%d", rows_per_carrier, error_rate, seed, retention_days)
    logger.info("==================================================")

    # 1. Ensure bucket exists
    storage.ensure_bucket()

    # 2. Enforce retention policy: Purge objects older than retention_days
    purged = storage.cleanup_retention(retention_days)

    # 3. Generate and deposit files for all 3 carriers
    batch_results: list[dict[str, Any]] = []

    target_export_dir = local_export_dir or Path("./data/latest")
    target_export_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        for carrier_id, config in sorted(CARRIERS_REGISTRY.items()):
            logger.info("Generating batch for Carrier %d (%s)...", carrier_id, config.name)
            sim = TypeCSimulator(carrier=config, seed=seed, error_rate=error_rate)

            fmt = config.default_format
            filename = f"carrier_{carrier_id}_events_{timestamp_str}.{fmt}"
            local_file = tmp_path / filename

            events = sim.generate_events(num_rows=rows_per_carrier, base_datetime=cycle_time)
            if fmt == "csv":
                sim.write_csv(events, local_file)
            else:
                sim.write_xlsx(events, local_file)

            sha256_hash = compute_file_sha256(local_file)
            file_size_bytes = local_file.stat().st_size

            # Save latest copies locally for direct carrier port downloads
            persistent_file = target_export_dir / f"carrier_{carrier_id}_latest.{fmt}"
            persistent_file.write_bytes(local_file.read_bytes())

            json_events_file = target_export_dir / f"carrier_{carrier_id}_latest.json"
            json_events_file.write_text(json.dumps(events, indent=2, default=str), encoding="utf-8")

            # Deposit into timestamped partition in MinIO / S3
            object_key = f"carrier_{carrier_id}/{date_folder}/{filename}"
            storage.upload_file(local_file, object_key)

            # Also deposit as "latest" for instant extraction via S3 API
            latest_key = f"carrier_{carrier_id}/latest.{fmt}"
            storage.upload_file(local_file, latest_key)

            download_url = storage.generate_presigned_url(object_key, expires_in=86400)

            result_entry = {
                "carrier_id": carrier_id,
                "carrier_code": config.code,
                "carrier_name": config.name,
                "format": fmt,
                "filename": filename,
                "local_path": str(persistent_file.resolve()),
                "object_key": object_key,
                "latest_key": latest_key,
                "sha256": sha256_hash,
                "size_bytes": file_size_bytes,
                "rows_generated": len(events),
                "download_url": download_url,
            }
            batch_results.append(result_entry)
            LATEST_STATE["carriers"][carrier_id] = {
                **result_entry,
                "events_sample": events[:5],
                "total_events": len(events),
            }
            logger.info("Successfully deposited '%s' (%d bytes, sha256=%s...)", object_key, file_size_bytes, sha256_hash[:12])

        # 4. Upload manifest for downstream consumers
        manifest = {
            "cycle_id": cycle_id,
            "generated_at": cycle_time.isoformat(),
            "carriers_count": len(batch_results),
            "retention_days": retention_days,
            "purged_old_files_count": len(purged),
            "batches": batch_results,
        }
        manifest_path = tmp_path / "latest_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        storage.upload_file(manifest_path, f"manifests/{cycle_id}.json", content_type="application/json")
        storage.upload_file(manifest_path, "manifests/latest.json", content_type="application/json")

        (target_export_dir / "latest_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        LATEST_STATE["cycle_id"] = cycle_id
        LATEST_STATE["last_updated"] = cycle_time.isoformat()

    logger.info("Cycle %s completed successfully. Deposited %d carrier files.", cycle_id, len(batch_results))
    return manifest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Type C Batch Carrier Periodic Generator and MinIO/S3 Depositor",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single generation and upload cycle, then terminate",
    )
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=float(os.getenv("INTERVAL_HOURS", "4.0")),
        help="Periodic cycle interval in hours (Default: 4 hours as per requirement F5)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=int(os.getenv("RETENTION_DAYS", "3")),
        help="Number of days to preserve carrier files before automatic purge",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=int(os.getenv("ROWS_PER_CARRIER", "100")),
        help="Number of event rows per carrier file",
    )
    parser.add_argument(
        "--error-rate",
        type=float,
        default=float(os.getenv("ERROR_RATE", "0.10")),
        help="Anomaly / defect injection rate between 0.0 and 1.0",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=int(os.getenv("SEED", "42")),
        help="Random seed for reproducible anomaly and data generation",
    )

    args = parser.parse_args(argv)

    storage = S3StorageManager()
    wait_for_storage(storage)

    if args.once:
        run_batch_cycle(
            storage=storage,
            rows_per_carrier=args.rows,
            error_rate=args.error_rate,
            seed=args.seed,
            retention_days=args.retention_days,
        )
        return

    interval_seconds = max(30.0, args.interval_hours * 3600.0)
    logger.info("Starting background scheduler: every %.1f hours (%.0f seconds).", args.interval_hours, interval_seconds)

    while True:
        try:
            run_batch_cycle(
                storage=storage,
                rows_per_carrier=args.rows,
                error_rate=args.error_rate,
                seed=args.seed,
                retention_days=args.retention_days,
            )
        except Exception as exc:
            logger.exception("Error during batch cycle: %s", exc)

        logger.info("Sleeping for %.1f hours (%.0f seconds) until next cycle...", args.interval_hours, interval_seconds)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()
