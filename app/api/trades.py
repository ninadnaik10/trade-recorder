from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.schemas import TradeRequest, TradeResponse
from app.core.database import get_db
from app.models.trade import Trade
from app.services.trade_ingestion import (
    DuplicateTradeConflictError,
    OversellError,
    ingest_trade as ingest_trade_service,
)
from app.services.trade_queries import (
    TradeNotFoundError,
    get_trade as get_trade_service,
    list_trades as list_trades_service,
)

router = APIRouter(prefix="/trades", tags=["trades"])


@router.get("", response_model=list[TradeResponse])
def list_trades(db: Annotated[Session, Depends(get_db)]) -> list[TradeResponse]:
    return [_to_response(trade) for trade in list_trades_service(db)]


@router.get("/{venue}/{trade_id}", response_model=TradeResponse)
def get_trade(
    venue: str,
    trade_id: str,
    db: Annotated[Session, Depends(get_db)],
) -> TradeResponse:
    try:
        return _to_response(get_trade_service(db, venue, trade_id))
    except TradeNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.post("", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
def ingest_trade(
    trade: TradeRequest,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> TradeResponse:
    try:
        result = ingest_trade_service(db, **trade.model_dump())
    except OversellError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    except DuplicateTradeConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    if not result.created:
        response.status_code = status.HTTP_200_OK

    return _to_response(result.trade)


def _to_response(stored_trade: Trade) -> TradeResponse:
    return TradeResponse(
        venue=stored_trade.venue,
        trade_id=stored_trade.trade_id,
        symbol=stored_trade.symbol,
        side=stored_trade.side,
        quantity=stored_trade.quantity,
        price=stored_trade.price,
        timestamp=stored_trade.timestamp,
    )
