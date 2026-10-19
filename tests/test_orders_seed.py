from datetime import date

import pytest
import pytest_asyncio
from simulators.seed.guards import (
    SeedGuardError,
    guard_app_environment,
    guard_database_host,
    guard_existing_orders,
)
from simulators.seed.orders_seed import (
    find_simulated_carriers,
    seed_day,
    seed_reference_data,
)
from simulators.seed.settings import SeedSettings
from sqlalchemy import BigInteger, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles

from app.database import Base
from app.models.brand import Brand
from app.models.carrier import Carrier
from app.models.distribution_center import DistributionCenter
from app.models.order import Order
from app.models.order_line import OrderLine
from app.models.order_recipient import OrderRecipient
from app.models.shipment_type import ShipmentType
from app.models.shipping_label import ShippingLabel
from app.models.state_mapping import CANONICAL_STATUSES


@compiles(BigInteger, "sqlite")
def compile_big_int_sqlite(element, compiler, **kwargs):
    return "INTEGER"


@pytest_asyncio.fixture
async def async_db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        session.add(Carrier(name="Seed Carrier", integration_type="simulated", status="active"))
        await session.commit()
        yield session
    await engine.dispose()


@pytest.fixture
def seed_settings():
    return SeedSettings(
        profile="dev",
        days=1,
        orders_per_day=12,
        start_date=date(2026, 10, 1),
        random_seed=42,
        allow_remote=False,
        app_env="development",
    )


async def _seed_one_day(session: AsyncSession, settings: SeedSettings) -> int:
    factory = async_sessionmaker(
        bind=session.bind,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with factory() as lookup_session:
        carriers = await find_simulated_carriers(lookup_session)
    brand_ids, center_ids, shipment_type_codes = await seed_reference_data(factory)
    return await seed_day(
        factory,
        settings.start_date,
        settings,
        brand_ids,
        center_ids,
        shipment_type_codes,
        carriers,
    )


@pytest.mark.asyncio
async def test_seed_inserts_related_order_data_and_is_idempotent(
    async_db_session: AsyncSession,
    seed_settings: SeedSettings,
):
    assert await _seed_one_day(async_db_session, seed_settings) == seed_settings.orders_per_day
    assert await _seed_one_day(async_db_session, seed_settings) == 0
    assert await async_db_session.scalar(select(func.count(Order.order_id))) == 12
    assert await async_db_session.scalar(select(func.count(OrderLine.order_line_id))) >= 12
    assert await async_db_session.scalar(select(func.count(OrderRecipient.order_id))) == 12
    assert await async_db_session.scalar(select(func.count(ShippingLabel.label_id))) == 12
    assert await async_db_session.scalar(select(func.count(Brand.brand_id))) == 3
    assert await async_db_session.scalar(select(func.count(DistributionCenter.dc_id))) == 3
    assert await async_db_session.scalar(select(func.count(ShipmentType.shipment_type_code))) == 2


@pytest.mark.asyncio
async def test_seed_data_is_deterministic_and_uses_canonical_statuses(
    async_db_session: AsyncSession,
    seed_settings: SeedSettings,
):
    await _seed_one_day(async_db_session, seed_settings)
    first = list(
        (
            await async_db_session.execute(
                select(Order.brand_order_ref, Order.status, ShippingLabel.tracking_number)
                .join(ShippingLabel)
                .order_by(Order.brand_order_ref)
            )
        ).all()
    )
    assert all(status in CANONICAL_STATUSES for _, status, _ in first)

    await async_db_session.execute(OrderRecipient.__table__.delete())
    await async_db_session.execute(OrderLine.__table__.delete())
    await async_db_session.execute(ShippingLabel.__table__.delete())
    await async_db_session.execute(Order.__table__.delete())
    await async_db_session.commit()
    await _seed_one_day(async_db_session, seed_settings)
    second = list(
        (
            await async_db_session.execute(
                select(Order.brand_order_ref, Order.status, ShippingLabel.tracking_number)
                .join(ShippingLabel)
                .order_by(Order.brand_order_ref)
            )
        ).all()
    )
    assert second == first


def test_production_environment_guard_refuses():
    with pytest.raises(SeedGuardError, match="APP_ENV"):
        guard_app_environment("production")


def test_remote_host_guard_refuses():
    with pytest.raises(SeedGuardError, match="remote database host"):
        guard_database_host("postgresql+asyncpg://user:password@remote.example/db", False)


@pytest.mark.asyncio
async def test_existing_non_seed_order_guard_refuses(async_db_session: AsyncSession):
    async_db_session.add_all(
        [
            Brand(name="Existing", tier="TIER_1"),
            DistributionCenter(
                code="EXISTING",
                name="Existing Center",
                city="City",
                country_code="CO",
            ),
            ShipmentType(shipment_type_code="EXISTING", description="Existing"),
        ]
    )
    await async_db_session.flush()
    brand = await async_db_session.scalar(select(Brand).where(Brand.name == "Existing"))
    center = await async_db_session.scalar(
        select(DistributionCenter).where(DistributionCenter.code == "EXISTING")
    )
    async_db_session.add(
        Order(
            brand_id=brand.brand_id,
            dc_id=center.dc_id,
            shipment_type_code="EXISTING",
            brand_order_ref="CUSTOM-ORDER",
            destination_country="CO",
            destination_region="Bogota",
            freight_value=1,
            status="CREATED",
        )
    )
    await async_db_session.commit()
    with pytest.raises(SeedGuardError, match="without the SEED- prefix"):
        await guard_existing_orders(async_db_session)


@pytest.mark.asyncio
async def test_missing_simulated_carrier_fails_clearly(async_db_session: AsyncSession):
    await async_db_session.execute(Carrier.__table__.delete())
    await async_db_session.commit()
    with pytest.raises(SeedGuardError, match="no simulated carriers found"):
        await find_simulated_carriers(async_db_session)
