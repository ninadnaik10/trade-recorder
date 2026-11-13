from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.trade import Trade


@dataclass(frozen=True)
class StatementTrade:
    venue: str
    trade_id: str
    symbol: str
    side: str
    quantity: Decimal
    price: Decimal
    timestamp: datetime


@dataclass(frozen=True)
class Mismatch:
    trade_id: str
    differences: dict[str, tuple[object, object]]


@dataclass(frozen=True)
class ReconciliationResult:
    missing: list[StatementTrade]
    extra: list[Trade]
    mismatched: list[Mismatch]


def reconcile(
    session: Session, venue: str, statement: list[StatementTrade]
) -> ReconciliationResult:
    stored_by_trade_id = {
        trade.trade_id: trade
        for trade in session.scalars(
            select(Trade).where(Trade.venue == venue).order_by(Trade.trade_id)
        )
    }
    statement_by_trade_id = {trade.trade_id: trade for trade in statement}

    missing = [
        statement_by_trade_id[trade_id]
        for trade_id in sorted(statement_by_trade_id.keys() - stored_by_trade_id.keys())
    ]
    extra = [
        stored_by_trade_id[trade_id]
        for trade_id in sorted(stored_by_trade_id.keys() - statement_by_trade_id.keys())
    ]
    mismatched = []
    for trade_id in sorted(stored_by_trade_id.keys() & statement_by_trade_id.keys()):
        differences = _differing_fields(
            stored_by_trade_id[trade_id], statement_by_trade_id[trade_id]
        )
        if differences:
            mismatched.append(Mismatch(trade_id=trade_id, differences=differences))
    return ReconciliationResult(missing=missing, extra=extra, mismatched=mismatched)


def _differing_fields(
    stored: Trade, statement: StatementTrade
) -> dict[str, tuple[object, object]]:
    fields = ("symbol", "side", "quantity", "price", "timestamp")
    return {
        field: (getattr(stored, field), getattr(statement, field))
        for field in fields
        if not _fields_match(field, getattr(stored, field), getattr(statement, field))
    }


def _fields_match(field: str, stored: object, statement: object) -> bool:
    if field != "timestamp":
        return stored == statement
    return _as_utc(stored) == _as_utc(statement)


def _as_utc(value: object) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("timestamp values must be datetimes")
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
