from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import api_router
from app.core.database import create_tables


@asynccontextmanager
async def lifespan(_: FastAPI):
    create_tables()
    yield

app = FastAPI(
    title="Trade Recorder & PnL Service",
    version="0.1.0",
    description="Backend service for trade ingestion, positions, PnL, and reconciliation.",
    lifespan=lifespan,
)

app.include_router(api_router)

