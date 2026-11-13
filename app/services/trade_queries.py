from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trade import Trade
from app.services.errors import TradeNotFoundError


def list_trades_page(
    session: Session,
    *,
    limit: int,
    cursor: int | None = None,
    venue: str | None = None,
    symbol: str | None = None,
) -> tuple[list[Trade], int | None]:
    query = select(Trade)
    if venue is not None:
        query = query.where(Trade.venue == venue)
    if symbol is not None:
        query = query.where(Trade.symbol == symbol)
    if cursor is not None:
        query = query.where(Trade.id > cursor)
    query = query.order_by(Trade.id).limit(limit + 1)

    trades = list(session.scalars(query))
    next_cursor = trades[limit - 1].id if len(trades) > limit else None
    return trades[:limit], next_cursor


def get_trade(session: Session, venue: str, trade_id: str) -> Trade:
    trade = session.scalar(select(Trade).where(Trade.venue == venue, Trade.trade_id == trade_id))
    if trade is None:
        raise TradeNotFoundError(f"no trade exists for venue={venue!r} and trade_id={trade_id!r}")
    return trade
