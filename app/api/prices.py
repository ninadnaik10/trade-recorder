from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas import LatestPriceRequest, LatestPriceResponse
from app.core.database import get_db
from app.models.market_price import MarketPrice
from app.services.errors import LatestPriceNotFoundError
from app.services.prices import (
    get_latest_price,
)
from app.services.prices import (
    set_latest_price as set_latest_price_service,
)

router = APIRouter(prefix="/prices", tags=["prices"])


@router.get("/{symbol}", response_model=LatestPriceResponse)
def get_price(symbol: str, db: Annotated[Session, Depends(get_db)]) -> LatestPriceResponse:
    try:
        return _to_response(get_latest_price(db, symbol))
    except LatestPriceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.put("/{symbol}", response_model=LatestPriceResponse)
def set_latest_price(
    symbol: str,
    price: LatestPriceRequest,
    db: Annotated[Session, Depends(get_db)],
) -> LatestPriceResponse:
    return _to_response(set_latest_price_service(db, symbol, price.price))


def _to_response(market_price: MarketPrice) -> LatestPriceResponse:
    return LatestPriceResponse(
        symbol=market_price.symbol,
        price=market_price.price,
        updated_at=market_price.updated_at,
    )
