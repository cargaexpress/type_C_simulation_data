from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.order import Order
    from app.models.picking_task import PickingTask
    from app.models.shipping_label_item import ShippingLabelItem


class OrderLine(Base):
    __tablename__ = "order_lines"

    order_line_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("orders.order_id"), nullable=False)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)
    sku: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="order_lines")
    picking_tasks: Mapped[list["PickingTask"]] = relationship(back_populates="order_line")
    label_items: Mapped[list["ShippingLabelItem"]] = relationship(back_populates="order_line")
