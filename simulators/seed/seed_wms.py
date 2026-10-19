"""Idempotent seed script and service for WMS and simulated carriers.

Ensures initialization or synchronization of:
1. ShipmentTypes (STANDARD, EXPRESS, SAME_DAY).
2. Distribution Centers (DCs).
3. Commercial brands (Brands).
4. Type C Carriers and their canonical status mappings in state_mapping.
5. Test orders (Orders), lines, recipients, and shipping labels (ShippingLabels).
"""

import os
import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from simulators.type_c.catalogs import CARRIERS_REGISTRY


@dataclass
class SeedConfig:
    seed: int = 42
    orders_count: int = 20
    carriers_to_seed: list[int] = None

    def __post_init__(self):
        if self.carriers_to_seed is None:
            self.carriers_to_seed = [1, 2, 3]


class WMSSeeder:
    """Idempotent seeder executor on PostgreSQL / WMS."""

    def __init__(self, session: AsyncSession, config: SeedConfig | None = None) -> None:
        self.session = session
        self.config = config or SeedConfig()
        self.rng = random.Random(self.config.seed)

    async def seed_shipment_types(self) -> dict[str, str]:
        """Seed standard shipment types if they do not exist."""
        from app.models.shipment_type import ShipmentType

        types = [
            ("STANDARD", "Standard ground shipping (3 to 5 days)"),
            ("EXPRESS", "Express priority shipping (24 to 48 hours)"),
            ("SAME_DAY", "Same day delivery in capital city"),
        ]
        created = {}
        for code, desc in types:
            stmt = select(ShipmentType).where(ShipmentType.shipment_type_code == code)
            result = await self.session.execute(stmt)
            obj = result.scalar_one_or_none()
            if not obj:
                obj = ShipmentType(shipment_type_code=code, description=desc)
                self.session.add(obj)
            created[code] = desc
        await self.session.flush()
        return created

    async def seed_distribution_centers(self) -> dict[str, int]:
        """Seed distribution centers if they do not exist."""
        from app.models.distribution_center import DistributionCenter

        dcs = [
            ("DC-BOG", "Bogota Hub Distribution Center", "Bogotá", "CO"),
            ("DC-MED", "Medellin Antioquia Distribution Center", "Medellín", "CO"),
            ("DC-CLO", "Occidente Cali Logistics Center", "Cali", "CO"),
        ]
        dc_ids = {}
        for code, name, city, country in dcs:
            stmt = select(DistributionCenter).where(DistributionCenter.code == code)
            result = await self.session.execute(stmt)
            obj = result.scalar_one_or_none()
            if not obj:
                obj = DistributionCenter(
                    code=code,
                    name=name,
                    city=city,
                    country_code=country,
                )
                self.session.add(obj)
                await self.session.flush()
            dc_ids[code] = obj.dc_id
        return dc_ids

    async def seed_brands(self) -> dict[str, int]:
        """Seed client brands if they do not exist."""
        from app.models.brand import Brand

        brands = [
            ("ModaExpress S.A.S.", "TIER_1"),
            ("ElectroTech Colombia", "TIER_1"),
            ("Hogar & Confort", "TIER_2"),
        ]
        brand_ids = {}
        for name, tier in brands:
            stmt = select(Brand).where(Brand.name == name)
            result = await self.session.execute(stmt)
            obj = result.scalar_one_or_none()
            if not obj:
                obj = Brand(name=name, tier=tier, is_active=True)
                self.session.add(obj)
                await self.session.flush()
            brand_ids[name] = obj.brand_id
        return brand_ids

    async def seed_carriers_and_mappings(self) -> dict[int, int]:
        """Seed Type C carriers and their canonical status mappings (HU-12 / RN-01)."""
        from app.models.carrier import Carrier
        from app.models.state_mapping import StateMapping

        carrier_db_ids: dict[int, int] = {}

        for c_id in self.config.carriers_to_seed:
            cfg = CARRIERS_REGISTRY[c_id]
            # Find or create carrier by name
            stmt = select(Carrier).where(Carrier.name == cfg.name)
            result = await self.session.execute(stmt)
            carrier_obj = result.scalar_one_or_none()

            if not carrier_obj:
                carrier_obj = Carrier(
                    name=cfg.name,
                    integration_type="batch_file",
                    status="active",
                )
                self.session.add(carrier_obj)
                await self.session.flush()

            carrier_db_ids[c_id] = carrier_obj.carrier_id

            # Synchronize canonical mappings catalog idempotently
            for raw_status, canonical_status in cfg.status_catalog.items():
                mapping_stmt = select(StateMapping).where(
                    StateMapping.carrier_id == carrier_obj.carrier_id,
                    StateMapping.raw_status == raw_status,
                )
                mapping_res = await self.session.execute(mapping_stmt)
                mapping_obj = mapping_res.scalar_one_or_none()

                if not mapping_obj:
                    mapping_obj = StateMapping(
                        carrier_id=carrier_obj.carrier_id,
                        raw_status=raw_status,
                        canonical_status=canonical_status,
                    )
                    self.session.add(mapping_obj)

        await self.session.flush()
        return carrier_db_ids

    async def seed_orders_and_labels(
        self,
        brand_ids: dict[str, int],
        dc_ids: dict[str, int],
        carrier_db_ids: dict[int, int],
    ) -> list[str]:
        """Generate deterministic test orders and shipping labels for file ingestion testing."""
        from app.models.order import Order
        from app.models.order_line import OrderLine
        from app.models.order_recipient import OrderRecipient
        from app.models.shipping_label import ShippingLabel

        generated_tracking_numbers: list[str] = []
        brand_id_list = list(brand_ids.values())
        dc_id_list = list(dc_ids.values())
        carrier_items = list(carrier_db_ids.items())  # [(1, db_id1), (2, db_id2), ...]

        for i in range(1, self.config.orders_count + 1):
            ref = f"ORD-SEED-{self.config.seed}-{i:04d}"
            # Check if order already exists for strict idempotency
            stmt = select(Order).where(Order.brand_order_ref == ref)
            res = await self.session.execute(stmt)
            order_obj = res.scalar_one_or_none()

            carrier_cfg_id, carrier_db_id = carrier_items[i % len(carrier_items)]
            tracking_num = f"WMS-TRK-{carrier_cfg_id}-{i:05d}"
            generated_tracking_numbers.append(tracking_num)

            if not order_obj:
                brand_id = brand_id_list[i % len(brand_id_list)]
                dc_id = dc_id_list[i % len(dc_id_list)]
                shipment_type = "STANDARD" if i % 2 == 0 else "EXPRESS"

                order_obj = Order(
                    brand_id=brand_id,
                    dc_id=dc_id,
                    shipment_type_code=shipment_type,
                    brand_order_ref=ref,
                    destination_country="CO",
                    destination_region="Cundinamarca",
                    freight_value=Decimal("15000.00"),
                    status="CREATED",
                )
                self.session.add(order_obj)
                await self.session.flush()

                # Order lines
                line = OrderLine(
                    order_id=order_obj.order_id,
                    line_number=1,
                    sku=f"SKU-{self.rng.randint(100, 999)}",
                    description="Seed test item",
                    quantity_ordered=self.rng.randint(1, 3),
                )
                self.session.add(line)

                # Order recipient
                recipient = OrderRecipient(
                    order_id=order_obj.order_id,
                    full_name=f"Test Customer {i}",
                    email=f"customer{i}@example.com",
                    phone="+573001234567",
                    address_line=f"Calle {10 + i} # {20 + i} - {30 + i}",
                    city="Bogotá",
                )
                self.session.add(recipient)

                # Shipping label
                label = ShippingLabel(
                    order_id=order_obj.order_id,
                    carrier_id=carrier_db_id,
                    tracking_number=tracking_num,
                    status="CREATED",
                    weight_kg=Decimal("1.500"),
                )
                self.session.add(label)

        await self.session.commit()
        return generated_tracking_numbers

    async def execute_full_seed(self) -> dict[str, Any]:
        """Execute full idempotent seeding pipeline."""
        st = await self.seed_shipment_types()
        dcs = await self.seed_distribution_centers()
        brands = await self.seed_brands()
        carriers = await self.seed_carriers_and_mappings()
        tracking_numbers = await self.seed_orders_and_labels(brands, dcs, carriers)

        return {
            "status": "success",
            "shipment_types_count": len(st),
            "distribution_centers_count": len(dcs),
            "brands_count": len(brands),
            "carriers_count": len(carriers),
            "tracking_numbers_count": len(tracking_numbers),
            "sample_tracking_numbers": tracking_numbers[:5],
        }


async def run_seed(
    database_url: str | None = None, config: SeedConfig | None = None
) -> dict[str, Any]:
    """Convenience function to run the seed against a PostgreSQL database."""
    db_url = database_url or os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL not specified and not present in environment variables.")

    engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        seeder = WMSSeeder(session=session, config=config)
        result = await seeder.execute_full_seed()

    await engine.dispose()
    return result
