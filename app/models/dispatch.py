from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.carrier import Carrier
    from app.models.distribution_center import DistributionCenter
    from app.models.shipping_label import ShippingLabel


class Dispatch(Base):
    __tablename__ = "dispatches"

    dispatch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    dc_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("distribution_centers.dc_id"), nullable=False
    )
    carrier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("carriers.carrier_id"), nullable=False
    )
    dispatched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    distribution_center: Mapped["DistributionCenter"] = relationship(back_populates="dispatches")
    carrier: Mapped["Carrier"] = relationship(back_populates="dispatches")
    shipping_labels: Mapped[list["ShippingLabel"]] = relationship(back_populates="dispatch")
