from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MarketPrice(Base):
    __tablename__ = "market_prices"
    __table_args__ = (CheckConstraint("price > 0", name="ck_market_prices_price_positive"),)

    symbol: Mapped[str] = mapped_column(String(100), primary_key=True)
    price: Mapped[Decimal] = mapped_column(Numeric(38, 18), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
