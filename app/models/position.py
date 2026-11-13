from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (CheckConstraint("quantity >= 0", name="ck_positions_quantity_nonnegative"),)

    symbol: Mapped[str] = mapped_column(String(100), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
