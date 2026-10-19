from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.brand import Brand
    from app.models.distribution_center import DistributionCenter
    from app.models.order_line import OrderLine
    from app.models.order_recipient import OrderRecipient
    from app.models.shipment_type import ShipmentType
    from app.models.shipping_label import ShippingLabel


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("brand_id", "brand_order_ref", name="uq_orders_brand_order_ref"),
        Index("ix_orders_brand_id", "brand_id"),
        Index("ix_orders_status", "status"),
    )

    order_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    brand_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("brands.brand_id"), nullable=False)
    dc_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("distribution_centers.dc_id"), nullable=False
    )
    shipment_type_code: Mapped[str] = mapped_column(
        String, ForeignKey("shipment_types.shipment_type_code"), nullable=False
    )
    brand_order_ref: Mapped[str] = mapped_column(String, nullable=False)
    destination_country: Mapped[str] = mapped_column(CHAR(2), nullable=False)
    destination_region: Mapped[str | None] = mapped_column(String, nullable=True)
    freight_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    brand: Mapped["Brand"] = relationship(back_populates="orders")
    distribution_center: Mapped["DistributionCenter"] = relationship(back_populates="orders")
    shipment_type: Mapped["ShipmentType"] = relationship(back_populates="orders")
    order_lines: Mapped[list["OrderLine"]] = relationship(back_populates="order")
    recipient: Mapped["OrderRecipient"] = relationship(back_populates="order", uselist=False)
    shipping_labels: Mapped[list["ShippingLabel"]] = relationship(back_populates="order")
