from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import PositionResponse
from app.core.database import get_db
from app.models.position import Position
from app.services.errors import PositionNotFoundError
from app.services.positions import (
    get_position as get_position_service,
)
from app.services.positions import (
    list_positions as list_positions_service,
)

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=list[PositionResponse])
def list_positions(db: Annotated[Session, Depends(get_db)]) -> list[PositionResponse]:
    return [_to_response(position) for position in list_positions_service(db)]


@router.get("/{symbol}", response_model=PositionResponse)
def get_position(symbol: str, db: Annotated[Session, Depends(get_db)]) -> PositionResponse:
    try:
        return _to_response(get_position_service(db, symbol))
    except PositionNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


def _to_response(position: Position) -> PositionResponse:
    return PositionResponse(
        symbol=position.symbol,
        quantity=position.quantity,
        average_cost=position.average_cost,
    )
