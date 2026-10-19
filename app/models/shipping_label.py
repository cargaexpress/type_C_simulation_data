from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
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
    from app.models.carrier import Carrier
    from app.models.dispatch import Dispatch
    from app.models.order import Order
    from app.models.shipping_label_item import ShippingLabelItem


class ShippingLabel(Base):
    __tablename__ = "shipping_labels"
    __table_args__ = (
        UniqueConstraint("tracking_number", name="uq_shipping_labels_tracking_number"),
        Index("ix_shipping_labels_order_id", "order_id"),
        Index("ix_shipping_labels_carrier_id", "carrier_id"),
    )

    label_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.order_id"), nullable=False)
    carrier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("carriers.carrier_id"), nullable=False
    )
    tracking_number: Mapped[str] = mapped_column(String, nullable=False)
    dispatch_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("dispatches.dispatch_id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String, nullable=False)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    order: Mapped["Order"] = relationship(back_populates="shipping_labels")
    carrier: Mapped["Carrier"] = relationship(back_populates="shipping_labels")
    dispatch: Mapped["Dispatch | None"] = relationship(back_populates="shipping_labels")
    label_items: Mapped[list["ShippingLabelItem"]] = relationship(back_populates="shipping_label")
