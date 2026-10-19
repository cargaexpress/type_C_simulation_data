from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.order_line import OrderLine


class PickingTask(Base):
    __tablename__ = "picking_tasks"

    picking_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_line_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("order_lines.order_line_id"), nullable=False
    )
    picker_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    quantity_picked: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    order_line: Mapped["OrderLine"] = relationship(back_populates="picking_tasks")
