# app/main.py
from fastapi import FastAPI

from app.api.routes import api_router

app = FastAPI(
    title="Trade Recorder & PnL Service",
    version="0.1.0",
    description="Backend service for trade ingestion, positions, PnL, and reconciliation.",
)
app.include_router(api_router)