from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_price import MarketPrice
from app.models.position import Position


class PositionNotFoundError(Exception):
    pass


@dataclass(frozen=True)
class PnlSnapshot:
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    latest_price: Decimal | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal | None


def list_pnl(session: Session) -> list[PnlSnapshot]:
    records = session.execute(
        select(Position, MarketPrice)
        .outerjoin(MarketPrice, MarketPrice.symbol == Position.symbol)
        .order_by(Position.symbol)
    ).all()
    return [_to_snapshot(position, market_price) for position, market_price in records]


def get_pnl(session: Session, symbol: str) -> PnlSnapshot:
    position = session.get(Position, symbol)
    if position is None:
        raise PositionNotFoundError(f"no position exists for {symbol}")

    return _to_snapshot(position, session.get(MarketPrice, symbol))


def _to_snapshot(position: Position, market_price: MarketPrice | None) -> PnlSnapshot:
    return PnlSnapshot(
        symbol=position.symbol,
        quantity=position.quantity,
        average_cost=position.average_cost,
        latest_price=market_price.price if market_price is not None else None,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=(
            position.quantity * (market_price.price - position.average_cost)
            if market_price is not None
            else None
        ),
    )
