"""Reproducible batch event file generator for Type C carriers (Source F5)."""

import csv
import hashlib
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import openpyxl

from simulators.type_c.catalogs import CarrierConfig, get_carrier_config
from simulators.type_c.corruption import apply_all_corruptions


class TypeCSimulator:
    """Batch event simulator for Type C carriers with defect injection."""

    def __init__(
        self,
        carrier: int | str | CarrierConfig,
        seed: int = 42,
        error_rate: float = 0.1,
    ) -> None:
        if isinstance(carrier, CarrierConfig):
            self.config = carrier
        else:
            self.config = get_carrier_config(carrier)

        self.seed = seed
        self.error_rate = max(0.0, min(1.0, error_rate))
        self.rng = random.Random(seed)

    def generate_events(
        self,
        num_rows: int = 100,
        universe_guides: list[str] | None = None,
        base_datetime: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Generate structured event list, applying defect injection if applicable."""
        if base_datetime is None:
            # Fixed and deterministic base datetime (UTC)
            base_datetime = datetime(2026, 10, 1, 8, 0, 0, tzinfo=UTC)

        # Determine universe of legitimate waybills
        events_per_guide = max(1, len(self.config.status_flow))
        num_guides = max(1, num_rows // events_per_guide + 1)

        if universe_guides:
            guides = universe_guides[:num_guides]
            while len(guides) < num_guides:
                guides.append(f"WMS-TRK-{self.config.carrier_id}-{len(guides) + 1:05d}")
        else:
            guides = [f"WMS-TRK-{self.config.carrier_id}-{i + 1:05d}" for i in range(num_guides)]

        raw_events: list[dict[str, Any]] = []

        hubs_c1 = ["BOGOTA_HUB", "MEDELLIN_HUB", "CALI_HUB", "BARRANQUILLA_HUB"]
        sucursales_c2 = [
            "Principal Bogotá",
            "Centro Medellín",
            "Occidente Cali",
            "Caribe Barranquilla",
        ]
        centers_c3 = ["DC-01", "DC-02", "DC-03", "DC-04"]

        for guide_idx, guide in enumerate(guides):
            guide_start_time = base_datetime.timestamp() + (guide_idx * 1800)  # +30 min per waybill

            for step_idx, raw_status in enumerate(self.config.status_flow):
                if len(raw_events) >= num_rows:
                    break

                event_epoch = guide_start_time + (step_idx * 7200)  # +2 hours per status
                event_dt = datetime.fromtimestamp(event_epoch, tz=UTC)
                formatted_dt = event_dt.strftime("%Y-%m-%d %H:%M:%S")

                if self.config.carrier_id == 1:
                    row = {
                        "waybill_no": guide,
                        "status_code": raw_status,
                        "status_description": f"Shipment status is {raw_status}",
                        "event_time": formatted_dt,
                        "hub_city": hubs_c1[(guide_idx + step_idx) % len(hubs_c1)],
                    }
                elif self.config.carrier_id == 2:
                    obs = (
                        "Operación normal"
                        if step_idx < len(self.config.status_flow) - 1
                        else "Completado"
                    )
                    row = {
                        "numero_guia": guide,
                        "estado_operativo": raw_status,
                        "fecha_hora_evento": formatted_dt,
                        "sucursal": sucursales_c2[(guide_idx + step_idx) % len(sucursales_c2)],
                        "observaciones": obs,
                    }
                elif self.config.carrier_id == 3:
                    row = {
                        "tracking_code": guide,
                        "code": raw_status,
                        "event_date": formatted_dt,
                        "center_id": centers_c3[(guide_idx + step_idx) % len(centers_c3)],
                    }
                else:
                    row = {
                        self.config.tracking_col: guide,
                        self.config.status_col: raw_status,
                        self.config.timestamp_col: formatted_dt,
                    }

                raw_events.append(row)

            if len(raw_events) >= num_rows:
                break

        # Orchestrated defect injection if error_rate > 0
        if self.error_rate > 0:
            final_events = apply_all_corruptions(
                rows=raw_events,
                columns=self.config.columns,
                tracking_col=self.config.tracking_col,
                status_col=self.config.status_col,
                timestamp_col=self.config.timestamp_col,
                rng=self.rng,
                error_rate=self.error_rate,
            )
        else:
            final_events = raw_events

        return final_events

    def write_csv(self, events: list[dict[str, Any]], output_path: Path) -> Path:
        """Write events to deterministic CSV file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=self.config.columns,
                extrasaction="ignore",
                lineterminator="\n",
            )
            writer.writeheader()
            for row in events:
                writer.writerow(row)

        return output_path

    def write_xlsx(self, events: list[dict[str, Any]], output_path: Path) -> Path:
        """Write events to deterministic Excel (.xlsx) file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = self.config.code

        # Write header
        ws.append(self.config.columns)

        # Write rows
        for row in events:
            row_vals = [row.get(col, "") for col in self.config.columns]
            ws.append(row_vals)

        wb.save(output_path)
        return output_path

    def generate_file(
        self,
        output_dir: Path | str,
        num_rows: int = 100,
        file_format: str | None = None,
        filename_prefix: str | None = None,
        universe_guides: list[str] | None = None,
    ) -> Path:
        """Generate dataset and write it in the specified format (csv or xlsx)."""
        target_dir = Path(output_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        fmt = (file_format or self.config.default_format).lower().strip().replace(".", "")
        if fmt not in {"csv", "xlsx"}:
            raise ValueError(f"Unsupported format: '{fmt}'. Only 'csv' or 'xlsx' are allowed.")

        prefix = filename_prefix or f"batch_{self.config.code.lower()}"
        filename = f"{prefix}_seed{self.seed}_err{int(self.error_rate * 100)}.{fmt}"
        target_path = target_dir / filename

        events = self.generate_events(num_rows=num_rows, universe_guides=universe_guides)

        if fmt == "csv":
            self.write_csv(events, target_path)
        else:
            self.write_xlsx(events, target_path)

        return target_path


def compute_file_sha256(file_path: Path) -> str:
    """Calculate SHA-256 hash of a file to validate exact reproducibility."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()
