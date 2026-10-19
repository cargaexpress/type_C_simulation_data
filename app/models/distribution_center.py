from typing import TYPE_CHECKING

from sqlalchemy import CHAR, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.dispatch import Dispatch
    from app.models.order import Order


class DistributionCenter(Base):
    __tablename__ = "distribution_centers"

    dc_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False)
    country_code: Mapped[str] = mapped_column(CHAR(2), nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="distribution_center")
    dispatches: Mapped[list["Dispatch"]] = relationship(back_populates="distribution_center")
