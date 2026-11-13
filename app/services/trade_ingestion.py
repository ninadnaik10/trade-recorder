from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.position import Position
from app.models.trade import Trade

ZERO = Decimal("0")


class DuplicateTradeConflictError(Exception):
    pass


class OversellError(Exception):
    pass


@dataclass(frozen=True)
class IngestionResult:
    trade: Trade
    created: bool


def ingest_trade(
    session: Session,
    *,
    venue: str,
    trade_id: str,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    timestamp: datetime,
) -> IngestionResult:
    try:
        with session.begin():
            existing = _find_trade(session, venue, trade_id)
            if existing is not None:
                return _existing_result(existing, symbol, side, quantity, price, timestamp)

            now = datetime.now(timezone.utc)
            session.execute(
                _insert_for_session(session, Position)
                .values(
                    symbol=symbol,
                    quantity=ZERO,
                    average_cost=ZERO,
                    realized_pnl=ZERO,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=["symbol"])
            )
            position = session.scalar(
                select(Position).where(Position.symbol == symbol).with_for_update()
            )
            if position is None:
                raise RuntimeError("position could not be created")
            _apply_to_position(position, side, quantity, price, now)

            trade = Trade(
                venue=venue,
                trade_id=trade_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                price=price,
                timestamp=timestamp,
                created_at=now,
            )
            session.add(trade)
        return IngestionResult(trade=trade, created=True)
    except IntegrityError:
        existing = _find_trade(session, venue, trade_id)
        if existing is not None:
            return _existing_result(existing, symbol, side, quantity, price, timestamp)
        raise


def _find_trade(session: Session, venue: str, trade_id: str) -> Trade | None:
    return session.scalar(select(Trade).where(Trade.venue == venue, Trade.trade_id == trade_id))


def _existing_result(
    existing: Trade,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    timestamp: datetime,
) -> IngestionResult:
    if (
        existing.symbol != symbol
        or existing.side != side
        or existing.quantity != quantity
        or existing.price != price
        or not _same_timestamp(existing.timestamp, timestamp)
    ):
        raise DuplicateTradeConflictError("venue and trade_id already identify a different trade")
    return IngestionResult(trade=existing, created=False)


def _same_timestamp(first: datetime, second: datetime) -> bool:
    return _as_utc(first) == _as_utc(second)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _insert_for_session(session: Session, model: type[Position]):
    if session.bind is None:
        raise RuntimeError("session is not bound to a database engine")
    if session.bind.dialect.name == "postgresql":
        return pg_insert(model)
    return sqlite_insert(model)


def _apply_to_position(
    position: Position,
    side: str,
    quantity: Decimal,
    price: Decimal,
    now: datetime,
) -> None:
    if side == "BUY":
        total_quantity = position.quantity + quantity
        position.average_cost = (
            (position.quantity * position.average_cost) + (quantity * price)
        ) / total_quantity
        position.quantity = total_quantity
        position.updated_at = now
        return

    if position.quantity < quantity:
        raise OversellError("sell quantity exceeds the current position")

    position.realized_pnl += quantity * (price - position.average_cost)
    position.quantity -= quantity
    if position.quantity == ZERO:
        position.average_cost = ZERO
    position.updated_at = now
