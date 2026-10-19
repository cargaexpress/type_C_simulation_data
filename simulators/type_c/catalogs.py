"""Catalogs and configurations for Type C carriers (Source F5)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CarrierConfig:
    """Schema configuration and proprietary catalog for a Type C carrier."""

    carrier_id: int
    code: str
    name: str
    default_format: str  # "csv" or "xlsx"
    columns: list[str]
    tracking_col: str
    status_col: str
    timestamp_col: str
    status_catalog: dict[str, str]  # {raw_status: canonical_status}
    status_flow: list[str]  # Typical expected raw_status sequence


# Carrier 1: TransExpress Logistics (Technical English, CSV)
CARRIER_1_CONFIG = CarrierConfig(
    carrier_id=1,
    code="CARRIER_1",
    name="TransExpress Logistics",
    default_format="csv",
    columns=[
        "waybill_no",
        "status_code",
        "status_description",
        "event_time",
        "hub_city",
    ],
    tracking_col="waybill_no",
    status_col="status_code",
    timestamp_col="event_time",
    status_catalog={
        "DOC_REC": "CREATED",
        "DISPATCHED": "PICKED_UP",
        "IN_DEPOT": "IN_TRANSIT",
        "OUT_DELIVERY": "OUT_FOR_DELIVERY",
        "INCIDENCE": "EXCEPTION",
        "DELIVERED": "DELIVERED",
        "RETURN_SENDER": "RETURNED",
        "DAMAGED_CARGO": "LOST_OR_DAMAGED",
    },
    status_flow=[
        "DOC_REC",
        "DISPATCHED",
        "IN_DEPOT",
        "OUT_DELIVERY",
        "DELIVERED",
    ],
)

# Carrier 2: Rápido Andino (Operational Spanish, XLSX)
CARRIER_2_CONFIG = CarrierConfig(
    carrier_id=2,
    code="CARRIER_2",
    name="Rápido Andino",
    default_format="xlsx",
    columns=[
        "numero_guia",
        "estado_operativo",
        "fecha_hora_evento",
        "sucursal",
        "observaciones",
    ],
    tracking_col="numero_guia",
    status_col="estado_operativo",
    timestamp_col="fecha_hora_evento",
    status_catalog={
        "REGISTRADO": "CREATED",
        "RECOLECTADO": "PICKED_UP",
        "TRASLADO_INTERNO": "IN_TRANSIT",
        "RUTA_ENTREGA": "OUT_FOR_DELIVERY",
        "NOVEDAD_DIRECCION": "EXCEPTION",
        "ENTREGADO_OK": "DELIVERED",
        "DEVUELTO_ORIGEN": "RETURNED",
        "EXTRAVIO": "LOST_OR_DAMAGED",
    },
    status_flow=[
        "REGISTRADO",
        "RECOLECTADO",
        "TRASLADO_INTERNO",
        "RUTA_ENTREGA",
        "ENTREGADO_OK",
    ],
)

# Carrier 3: Logística 360 (Numeric codes, CSV)
CARRIER_3_CONFIG = CarrierConfig(
    carrier_id=3,
    code="CARRIER_3",
    name="Logística 360",
    default_format="csv",
    columns=[
        "tracking_code",
        "code",
        "event_date",
        "center_id",
    ],
    tracking_col="tracking_code",
    status_col="code",
    timestamp_col="event_date",
    status_catalog={
        "10": "CREATED",
        "20": "PICKED_UP",
        "30": "IN_TRANSIT",
        "40": "OUT_FOR_DELIVERY",
        "50": "EXCEPTION",
        "90": "DELIVERED",
        "91": "RETURNED",
        "99": "LOST_OR_DAMAGED",
    },
    status_flow=[
        "10",
        "20",
        "30",
        "40",
        "90",
    ],
)

CARRIERS_REGISTRY: dict[int, CarrierConfig] = {
    1: CARRIER_1_CONFIG,
    2: CARRIER_2_CONFIG,
    3: CARRIER_3_CONFIG,
}


def get_carrier_config(carrier_id: int | str) -> CarrierConfig:
    """Retrieve carrier configuration by numeric ID or code."""
    if isinstance(carrier_id, str):
        # Convert carrier_1 -> 1 if applicable, or parse int
        normalized = carrier_id.strip().upper()
        if normalized in {"1", "CARRIER_1", "CARRIER1"}:
            c_id = 1
        elif normalized in {"2", "CARRIER_2", "CARRIER2"}:
            c_id = 2
        elif normalized in {"3", "CARRIER_3", "CARRIER3"}:
            c_id = 3
        else:
            try:
                c_id = int(carrier_id)
            except ValueError as exc:
                raise ValueError(
                    f"Invalid carrier identifier: '{carrier_id}'. Valid options: 1, 2, 3."
                ) from exc
    else:
        c_id = carrier_id

    if c_id not in CARRIERS_REGISTRY:
        raise ValueError(
            f"Type C carrier with ID {c_id} is not registered. Valid options: 1, 2, 3."
        )

    return CARRIERS_REGISTRY[c_id]
