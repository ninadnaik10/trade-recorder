
from fastapi import APIRouter

from app.api import pnl, positions, prices, reconciliation, trades

api_router = APIRouter()
api_router.include_router(trades.router)
api_router.include_router(positions.router)
api_router.include_router(prices.router)
api_router.include_router(pnl.router)
api_router.include_router(reconciliation.router)
