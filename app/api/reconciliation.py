from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import (
    MismatchedTrade,
    MismatchValues,
    ReconciliationRequest,
    ReconciliationResponse,
    TradeResponse,
)
from app.core.database import get_db
from app.models.trade import Trade
from app.services.reconciliation import StatementTrade, reconcile

router = APIRouter(prefix="/reconcile", tags=["reconciliation"])


@router.post("/{venue}", response_model=ReconciliationResponse)
def reconcile_venue(
    venue: str,
    statement: ReconciliationRequest,
    db: Annotated[Session, Depends(get_db)],
) -> ReconciliationResponse:
    if any(trade.venue != venue for trade in statement.trades):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="every statement trade must match the venue in the path",
        )

    result = reconcile(
        db,
        venue,
        [
            StatementTrade(
                venue=trade.venue,
                trade_id=trade.trade_id,
                symbol=trade.symbol,
                side=trade.side,
                quantity=trade.quantity,
                price=trade.price,
                timestamp=trade.timestamp,
            )
            for trade in statement.trades
        ],
    )
    return ReconciliationResponse(
        missing=[_statement_to_response(trade) for trade in result.missing],
        extra=[_trade_to_response(trade) for trade in result.extra],
        mismatched=[
            MismatchedTrade(
                trade_id=mismatch.trade_id,
                differences={
                    field: MismatchValues(
                        stored=_format_value(values[0]),
                        statement=_format_value(values[1]),
                    )
                    for field, values in mismatch.differences.items()
                },
            )
            for mismatch in result.mismatched
        ],
    )


def _statement_to_response(trade: StatementTrade) -> TradeResponse:
    return TradeResponse(
        venue=trade.venue,
        trade_id=trade.trade_id,
        symbol=trade.symbol,
        side=trade.side,
        quantity=trade.quantity,
        price=trade.price,
        timestamp=trade.timestamp,
    )


def _trade_to_response(trade: Trade) -> TradeResponse:
    return TradeResponse(
        venue=trade.venue,
        trade_id=trade.trade_id,
        symbol=trade.symbol,
        side=trade.side,
        quantity=trade.quantity,
        price=trade.price,
        timestamp=trade.timestamp,
    )


def _format_value(value: object) -> str:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)
