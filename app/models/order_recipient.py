from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.order import Order


class OrderRecipient(Base):
    __tablename__ = "order_recipients"

    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.order_id"), primary_key=True
    )
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    address_line: Mapped[str] = mapped_column(String, nullable=False)
    city: Mapped[str] = mapped_column(String, nullable=False)

    order: Mapped["Order"] = relationship(back_populates="recipient")
