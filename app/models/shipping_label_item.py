from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.order_line import OrderLine
    from app.models.shipping_label import ShippingLabel


class ShippingLabelItem(Base):
    __tablename__ = "shipping_label_items"

    label_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("shipping_labels.label_id"), primary_key=True
    )
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.order_id"), nullable=False)
    order_line_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_lines.order_line_id"), primary_key=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    shipping_label: Mapped["ShippingLabel"] = relationship(back_populates="label_items")
    order_line: Mapped["OrderLine"] = relationship(back_populates="label_items")
