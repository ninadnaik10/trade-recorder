from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.market_price import MarketPrice


class LatestPriceNotFoundError(Exception):
    pass


def get_latest_price(session: Session, symbol: str) -> MarketPrice:
    market_price = session.get(MarketPrice, symbol)
    if market_price is None:
        raise LatestPriceNotFoundError(f"no latest price exists for {symbol}")
    return market_price


def set_latest_price(session: Session, symbol: str, price: Decimal) -> MarketPrice:
    now = datetime.now(timezone.utc)
    with session.begin():
        session.execute(
            _insert_for_session(session, MarketPrice)
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


def _insert_for_session(session: Session, model: type[MarketPrice]):
    if session.bind is None:
        raise RuntimeError("session is not bound to a database engine")
    if session.bind.dialect.name == "postgresql":
        return pg_insert(model)
    return sqlite_insert(model)
