from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import PnlResponse
from app.core.database import get_db
from app.services.pnl import (
    PositionNotFoundError,
    PnlSnapshot,
    get_pnl as get_pnl_service,
    list_pnl as list_pnl_service,
)

router = APIRouter(prefix="/pnl", tags=["pnl"])


@router.get("", response_model=list[PnlResponse])
def list_pnl(db: Annotated[Session, Depends(get_db)]) -> list[PnlResponse]:
    return [_to_response(snapshot) for snapshot in list_pnl_service(db)]


@router.get("/{symbol}", response_model=PnlResponse)
def get_pnl(symbol: str, db: Annotated[Session, Depends(get_db)]) -> PnlResponse:
    try:
        return _to_response(get_pnl_service(db, symbol))
    except PositionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


def _to_response(snapshot: PnlSnapshot) -> PnlResponse:
    return PnlResponse(
        symbol=snapshot.symbol,
        quantity=snapshot.quantity,
        average_cost=snapshot.average_cost,
        latest_price=snapshot.latest_price,
        realized_pnl=snapshot.realized_pnl,
        unrealized_pnl=snapshot.unrealized_pnl,
    )
