from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dispatch import Dispatch
    from app.models.shipping_label import ShippingLabel


class Carrier(Base):
    __tablename__ = "carriers"

    carrier_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    integration_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    shipping_labels: Mapped[list["ShippingLabel"]] = relationship(back_populates="carrier")
    dispatches: Mapped[list["Dispatch"]] = relationship(back_populates="carrier")
