import logging
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.brand import Brand
from app.models.carrier import Carrier
from app.models.distribution_center import DistributionCenter
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.order_recipient import OrderRecipient
from app.models.shipment_type import ShipmentType
from app.models.shipping_label import ShippingLabel
from app.models.state_mapping import CANONICAL_STATUSES
from simulators.seed.guards import SEED_PREFIX, SeedGuardError
from simulators.seed.settings import SeedSettings

LOGGER = logging.getLogger(__name__)
ADVISORY_LOCK_KEY = 1_397_046_597
SECONDS_PER_DAY = 86_400
FIRST_SEQUENCE = 1
MIN_LINE_COUNT = 1
MAX_LINE_COUNT = 3
MIN_LINE_QUANTITY = 1
MAX_LINE_QUANTITY = 5
MAX_SKU_NUMBER = 999_999
MIN_FREIGHT_CENTS = 100
MAX_FREIGHT_CENTS = 500_000
CENTS_PER_UNIT = 100
MIN_WEIGHT_GRAMS = 100
MAX_WEIGHT_GRAMS = 50_000
GRAMS_PER_KILOGRAM = 1_000
MIN_PHONE_NUMBER = 2_000_000_000
MAX_PHONE_NUMBER = 9_999_999_999
MAX_ADDRESS_NUMBER = 9_999
STATUS_WEIGHTS = (10, 10, 20, 10, 5, 40, 3, 2)
DESTINATIONS = (
    ("CO", "Bogota District", "Bogota"),
    ("MX", "Mexico City", "Mexico City"),
    ("CL", "Metropolitan Region", "Santiago"),
    ("PE", "Lima Province", "Lima"),
)
FIRST_NAMES = ("Alex", "Casey", "Jordan", "Morgan", "Riley", "Taylor")
LAST_NAMES = ("Anderson", "Bennett", "Carter", "Diaz", "Parker", "Reed")
LINE_DESCRIPTIONS = ("Apparel item", "Home goods", "Electronic accessory", "Personal care")
REFERENCE_BRANDS = (
    ("SEED Brand 01", "TIER_1"),
    ("SEED Brand 02", "TIER_2"),
    ("SEED Brand 03", "TIER_1"),
)
REFERENCE_CENTERS = (
    ("SEED-BOG", "Seed Bogota Center", "Bogota", "CO"),
    ("SEED-MDE", "Seed Medellin Center", "Medellin", "CO"),
    ("SEED-CLO", "Seed Cali Center", "Cali", "CO"),
)
REFERENCE_SHIPMENT_TYPES = (
    ("SEED-STD", "Seed standard shipment"),
    ("SEED-EXP", "Seed express shipment"),
)


@asynccontextmanager
async def seed_run_lock(engine: AsyncEngine) -> AsyncIterator[None]:
    if engine.dialect.name != "postgresql":
        yield
        return

    # Serialize reference creation because brand names and center codes are not unique.
    async with engine.connect() as connection:
        await connection.execute(
            text("SELECT pg_advisory_lock(:lock_key)"), {"lock_key": ADVISORY_LOCK_KEY}
        )
        await connection.commit()
        try:
            yield
        finally:
            await connection.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"), {"lock_key": ADVISORY_LOCK_KEY}
            )
            await connection.commit()


async def find_simulated_carriers(session: AsyncSession) -> list[Carrier]:
    carriers = list(
        (
            await session.scalars(
                select(Carrier)
                .where(Carrier.integration_type == "simulated")
                .order_by(Carrier.carrier_id)
            )
        ).all()
    )
    if not carriers:
        raise SeedGuardError(
            "Seed refused: no simulated carriers found; apply the Alembic migrations first."
        )
    return carriers


async def seed_reference_data(
    session_factory: async_sessionmaker[AsyncSession],
) -> tuple[list[int], list[int], list[str]]:
    async with session_factory() as session, session.begin():
        brands: list[Brand] = []
        for name, tier in REFERENCE_BRANDS:
            brand = await session.scalar(
                select(Brand).where(Brand.name == name).order_by(Brand.brand_id).limit(1)
            )
            if brand is None:
                brand = Brand(name=name, tier=tier, is_active=True)
                session.add(brand)
                await session.flush()
            brands.append(brand)

        centers: list[DistributionCenter] = []
        for code, name, city, country_code in REFERENCE_CENTERS:
            center = await session.scalar(
                select(DistributionCenter)
                .where(DistributionCenter.code == code)
                .order_by(DistributionCenter.dc_id)
                .limit(1)
            )
            if center is None:
                center = DistributionCenter(
                    code=code,
                    name=name,
                    city=city,
                    country_code=country_code,
                )
                session.add(center)
                await session.flush()
            centers.append(center)

        shipment_types: list[ShipmentType] = []
        for code, description in REFERENCE_SHIPMENT_TYPES:
            shipment_type = await session.get(ShipmentType, code)
            if shipment_type is None:
                shipment_type = ShipmentType(shipment_type_code=code, description=description)
                session.add(shipment_type)
            shipment_types.append(shipment_type)
        await session.flush()

        return (
            [brand.brand_id for brand in brands],
            [center.dc_id for center in centers],
            [shipment_type.shipment_type_code for shipment_type in shipment_types],
        )


def _generate_day_rows(
    day: date,
    orders_per_day: int,
    random_seed: int,
    brand_ids: list[int],
    center_ids: list[int],
    shipment_type_codes: list[str],
    carriers: list[Carrier],
) -> list[dict[str, Any]]:
    rng = random.Random(f"{random_seed}:{day.isoformat()}")
    start = datetime.combine(day, time.min, tzinfo=UTC)
    generated: list[dict[str, Any]] = []
    for sequence in range(FIRST_SEQUENCE, orders_per_day + FIRST_SEQUENCE):
        reference = f"SEED-{day:%Y%m%d}-{sequence:06d}"
        status = rng.choices(CANONICAL_STATUSES, weights=STATUS_WEIGHTS, k=1)[0]
        index = sequence - FIRST_SEQUENCE
        country, region, city = DESTINATIONS[index % len(DESTINATIONS)]
        line_count = rng.randint(MIN_LINE_COUNT, MAX_LINE_COUNT)
        carrier = carriers[index % len(carriers)]
        line_rows = [
            {
                "line_number": line_number,
                "sku": f"SEED-SKU-{rng.randint(FIRST_SEQUENCE, MAX_SKU_NUMBER):06d}",
                "description": rng.choice(LINE_DESCRIPTIONS),
                "quantity_ordered": rng.randint(MIN_LINE_QUANTITY, MAX_LINE_QUANTITY),
            }
            for line_number in range(FIRST_SEQUENCE, line_count + FIRST_SEQUENCE)
        ]
        generated.append(
            {
                "order": {
                    "brand_id": brand_ids[index % len(brand_ids)],
                    "dc_id": center_ids[index % len(center_ids)],
                    "shipment_type_code": shipment_type_codes[index % len(shipment_type_codes)],
                    "brand_order_ref": reference,
                    "destination_country": country,
                    "destination_region": region,
                    "freight_value": Decimal(rng.randint(MIN_FREIGHT_CENTS, MAX_FREIGHT_CENTS))
                    / Decimal(CENTS_PER_UNIT),
                    "status": status,
                    "created_at": start
                    + timedelta(seconds=index * SECONDS_PER_DAY // orders_per_day),
                },
                "recipient": {
                    "full_name": (f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"),
                    "email": f"seed-{sequence:06d}@example.invalid",
                    "phone": f"+1{rng.randint(MIN_PHONE_NUMBER, MAX_PHONE_NUMBER)}",
                    "address_line": f"{rng.randint(FIRST_SEQUENCE, MAX_ADDRESS_NUMBER)} Seed Street",
                    "city": city,
                },
                "lines": line_rows,
                "label": {
                    "carrier_id": carrier.carrier_id,
                    "tracking_number": (
                        f"SEED-TRK-{carrier.carrier_id}-{day:%Y%m%d}-{sequence:06d}"
                    ),
                    "status": status,
                    "weight_kg": Decimal(rng.randint(MIN_WEIGHT_GRAMS, MAX_WEIGHT_GRAMS))
                    / Decimal(GRAMS_PER_KILOGRAM),
                },
            }
        )
    return generated


async def seed_day(
    session_factory: async_sessionmaker[AsyncSession],
    day: date,
    settings: SeedSettings,
    brand_ids: list[int],
    center_ids: list[int],
    shipment_type_codes: list[str],
    carriers: list[Carrier],
) -> int:
    generated = _generate_day_rows(
        day,
        settings.orders_per_day,
        settings.random_seed,
        brand_ids,
        center_ids,
        shipment_type_codes,
        carriers,
    )
    async with session_factory() as session, session.begin():
        existing_refs = set(
            (
                await session.scalars(
                    select(Order.brand_order_ref).where(
                        Order.brand_order_ref.startswith(f"{SEED_PREFIX}{day:%Y%m%d}-")
                    )
                )
            ).all()
        )
        pending = [row for row in generated if row["order"]["brand_order_ref"] not in existing_refs]
        if not pending:
            return 0

        result = await session.execute(
            insert(Order).returning(Order.order_id, Order.brand_order_ref),
            [row["order"] for row in pending],
        )
        order_ids = {reference: order_id for order_id, reference in result}

        recipients = []
        lines = []
        labels = []
        for row in pending:
            reference = row["order"]["brand_order_ref"]
            order_id = order_ids[reference]
            recipients.append({"order_id": order_id, **row["recipient"]})
            lines.extend({"order_id": order_id, **line_row} for line_row in row["lines"])
            labels.append({"order_id": order_id, **row["label"]})

        await session.execute(insert(OrderRecipient), recipients)
        await session.execute(insert(OrderLine), lines)
        await session.execute(insert(ShippingLabel), labels)
        return len(pending)


async def run_seed(engine: AsyncEngine, settings: SeedSettings, database_url: str) -> int:
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    total_inserted = 0
    async with seed_run_lock(engine):
        async with session_factory() as session:
            from simulators.seed.guards import run_guards

            await run_guards(
                session,
                settings.app_env,
                database_url,
                settings.allow_remote,
            )
            carriers = await find_simulated_carriers(session)

        brand_ids, center_ids, shipment_type_codes = await seed_reference_data(session_factory)
        for offset in range(settings.days):
            day = settings.start_date + timedelta(days=offset)
            inserted = await seed_day(
                session_factory,
                day,
                settings,
                brand_ids,
                center_ids,
                shipment_type_codes,
                carriers,
            )
            LOGGER.info(
                "date=%s inserted=%d requested=%d",
                day.isoformat(),
                inserted,
                settings.orders_per_day,
            )
            total_inserted += inserted
    LOGGER.info("total_inserted=%d", total_inserted)
    return total_inserted
