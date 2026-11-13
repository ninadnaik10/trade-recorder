from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.models.market_price import MarketPrice
from app.services.errors import LatestPriceNotFoundError


def get_latest_price(session: Session, symbol: str) -> MarketPrice:
    market_price = session.get(MarketPrice, symbol)
    if market_price is None:
        raise LatestPriceNotFoundError(f"no latest price exists for {symbol}")
    return market_price


def set_latest_price(session: Session, symbol: str, price: Decimal) -> MarketPrice:
    now = datetime.now(UTC)
    with session.begin():
        session.execute(
            pg_insert(MarketPrice)
            .values(symbol=symbol, price=price, updated_at=now)
            .on_conflict_do_update(
                index_elements=["symbol"],
                set_={"price": price, "updated_at": now},
            )
        )
        market_price = session.get(MarketPrice, symbol)
        if market_price is None:
            raise RuntimeError("latest price could not be created")
    return market_price
