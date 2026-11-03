"""FastAPI HTTP servers for Type C carriers.

Exposes individual HTTP endpoints/ports for each transportadora (Carrier 1, 2, and 3),
mirroring the accessibility model of Simulator Type B while fulfilling F5 batch object storage.
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from simulators.type_c.catalogs import CARRIERS_REGISTRY, get_carrier_config
from simulators.type_c.scheduler import (
    LATEST_STATE,
    run_batch_cycle,
    wait_for_storage,
)
from simulators.type_c.storage import S3StorageManager

logger = logging.getLogger("type_c_server")

DATA_DIR = Path(os.getenv("EXPORT_DATA_DIR", "./data/latest"))


def create_carrier_app(carrier_id: int) -> FastAPI:
    """Create a FastAPI application dedicated to a single carrier on its own port."""
    config = get_carrier_config(carrier_id)
    fmt = config.default_format
    carrier_prefix = f"/carrier-{carrier_id}"

    app = FastAPI(
        title=f"CargaExpress - Transportadora {carrier_id} ({config.name})",
        description=(
            f"API Endpoint para Transportadora Tipo C - {config.name}.\n\n"
            f"- **Formato**: `{fmt.upper()}`\n"
            f"- **Periodicidad**: Lote generado cada 4 horas\n"
            f"- **Almacenamiento**: MinIO / S3 Object Storage + Descarga directa\n"
        ),
        version="1.0.0",
        openapi_url=f"{carrier_prefix}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    @app.get("/openapi.json", include_in_schema=False)
    def root_openapi():
        return app.openapi()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/", summary="Información del estado del lote")
    def get_info() -> dict[str, Any]:
        info = LATEST_STATE["carriers"].get(carrier_id, {})
        return {
            "carrier_id": carrier_id,
            "carrier_code": config.code,
            "carrier_name": config.name,
            "format": fmt,
            "description": f"Carrier {carrier_id} - {config.name} ({fmt.upper()} Batch)",
            "cycle_id": LATEST_STATE.get("cycle_id"),
            "last_cycle_timestamp": LATEST_STATE.get("last_updated"),
            "total_rows_in_latest_batch": info.get("rows_generated", 0),
            "sha256": info.get("sha256"),
            "object_key_s3": info.get("object_key"),
            "direct_download_url": "/download",
            "events_json_url": "/events",
            "health_url": "/health",
        }

    @app.get("/health", summary="Healthcheck del servicio")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "carrier_id": carrier_id,
            "carrier_name": config.name,
            "format": fmt,
        }

    @app.get("/download", summary="Descargar el archivo más reciente (CSV o XLSX)")
    def download_latest_file():
        file_path = DATA_DIR / f"carrier_{carrier_id}_latest.{fmt}"
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="El archivo aún no ha sido generado por el ciclo.")

        media_type = "text/csv" if fmt == "csv" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"carrier_{carrier_id}_latest.{fmt}"
        return FileResponse(
            path=file_path,
            filename=filename,
            media_type=media_type,
        )

    @app.get("/events", summary="Obtener los eventos del lote en formato JSON")
    def get_latest_events():
        json_path = DATA_DIR / f"carrier_{carrier_id}_latest.json"
        if not json_path.exists():
            raise HTTPException(status_code=404, detail="Los eventos del lote aún no están disponibles.")
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            return JSONResponse(content={"carrier_id": carrier_id, "count": len(data), "events": data})
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error leyendo eventos: {exc}")

    @app.post("/generate", summary="Forzar la generación inmediata del lote")
    def force_generation():
        storage = S3StorageManager()
        manifest = run_batch_cycle(
            storage=storage,
            rows_per_carrier=int(os.getenv("ROWS_PER_CARRIER", "100")),
            error_rate=float(os.getenv("ERROR_RATE", "0.10")),
            seed=int(os.getenv("SEED", "42")),
            retention_days=int(os.getenv("RETENTION_DAYS", "3")),
            local_export_dir=DATA_DIR,
        )
        return {"status": "ok", "message": "Nuevo lote generado con éxito", "cycle_id": manifest.get("cycle_id")}

    return app


carrier_1_app = create_carrier_app(1)
carrier_2_app = create_carrier_app(2)
carrier_3_app = create_carrier_app(3)


async def run_periodic_scheduler(
    storage: S3StorageManager,
    interval_hours: float,
    rows: int,
    error_rate: float,
    seed: int,
    retention_days: int,
):
    """Run periodic generation loop every interval_hours in the background."""
    interval_seconds = max(30.0, interval_hours * 3600.0)
    logger.info("Scheduler background task running every %.1f hours (%.0f s).", interval_hours, interval_seconds)

    while True:
        try:
            logger.info("Triggering scheduled 4-hour batch cycle...")
            run_batch_cycle(
                storage=storage,
                rows_per_carrier=rows,
                error_rate=error_rate,
                seed=seed,
                retention_days=retention_days,
                local_export_dir=DATA_DIR,
            )
        except Exception as exc:
            logger.exception("Error during scheduled batch cycle: %s", exc)

        await asyncio.sleep(interval_seconds)


async def main():
    """Main entrypoint: connect to MinIO, run initial batch, and serve carrier ports 8005, 8006, 8007."""
    storage = S3StorageManager()
    wait_for_storage(storage)

    rows = int(os.getenv("ROWS_PER_CARRIER", "100"))
    error_rate = float(os.getenv("ERROR_RATE", "0.10"))
    seed = int(os.getenv("SEED", "42"))
    retention_days = int(os.getenv("RETENTION_DAYS", "3"))
    interval_hours = float(os.getenv("INTERVAL_HOURS", "4.0"))

    # Initial batch generation cycle on startup
    logger.info("Generating initial Type C batch files on startup...")
    run_batch_cycle(
        storage=storage,
        rows_per_carrier=rows,
        error_rate=error_rate,
        seed=seed,
        retention_days=retention_days,
        local_export_dir=DATA_DIR,
    )

    port_1 = int(os.getenv("PORT_CARRIER_1", "8005"))
    port_2 = int(os.getenv("PORT_CARRIER_2", "8006"))
    port_3 = int(os.getenv("PORT_CARRIER_3", "8007"))

    cfg_1 = uvicorn.Config(carrier_1_app, host="0.0.0.0", port=port_1, log_level="info")
    cfg_2 = uvicorn.Config(carrier_2_app, host="0.0.0.0", port=port_2, log_level="info")
    cfg_3 = uvicorn.Config(carrier_3_app, host="0.0.0.0", port=port_3, log_level="info")

    srv_1 = uvicorn.Server(cfg_1)
    srv_2 = uvicorn.Server(cfg_2)
    srv_3 = uvicorn.Server(cfg_3)

    logger.info("Starting Carrier HTTP services:")
    logger.info(" -> Transportadora 1 (CSV)        on port %d", port_1)
    logger.info(" -> Transportadora 2 (Excel XLSX) on port %d", port_2)
    logger.info(" -> Transportadora 3 (CSV Num)    on port %d", port_3)

    await asyncio.gather(
        srv_1.serve(),
        srv_2.serve(),
        srv_3.serve(),
        run_periodic_scheduler(storage, interval_hours, rows, error_rate, seed, retention_days),
    )


if __name__ == "__main__":
    asyncio.run(main())
