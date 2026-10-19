from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.order import Order


class ShipmentType(Base):
    __tablename__ = "shipment_types"

    shipment_type_code: Mapped[str] = mapped_column(String, primary_key=True)
    description: Mapped[str] = mapped_column(String, nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="shipment_type")
