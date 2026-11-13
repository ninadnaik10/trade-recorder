from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
PositiveDecimalString = Annotated[
    Decimal,
    Field(gt=Decimal("0"), max_digits=38, decimal_places=18),
]


def _require_decimal_string(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("must be a non-empty decimal string")
    return value.strip()


class TradeRequest(BaseModel):
    venue: NonEmptyText
    trade_id: NonEmptyText
    symbol: NonEmptyText
    side: Literal["BUY", "SELL"]
    quantity: PositiveDecimalString
    price: PositiveDecimalString
    timestamp: datetime

    @field_validator("quantity", "price", mode="before")
    @classmethod
    def require_decimal_string(cls, value: object) -> str:
        return _require_decimal_string(value)

    @field_validator("timestamp", mode="before")
    @classmethod
    def require_timestamp_string(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("must be a non-empty ISO 8601 timestamp string")
        return value.strip()

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("must include a timezone")
        return value.astimezone(timezone.utc)


class TradeResponse(BaseModel):
    venue: str
    trade_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    price: Decimal
    timestamp: datetime


class PositionResponse(BaseModel):
    symbol: str
    quantity: Decimal
    average_cost: Decimal


class LatestPriceRequest(BaseModel):
    price: PositiveDecimalString

    @field_validator("price", mode="before")
    @classmethod
    def require_decimal_string(cls, value: object) -> str:
        return _require_decimal_string(value)


class LatestPriceResponse(BaseModel):
    symbol: str
    price: Decimal
    updated_at: datetime


class PnlResponse(BaseModel):
    symbol: str
    quantity: Decimal
    average_cost: Decimal
    latest_price: Decimal | None
    realized_pnl: Decimal
    unrealized_pnl: Decimal | None


class ReconciliationRequest(BaseModel):
    trades: list[TradeRequest]

    @model_validator(mode="after")
    def require_unique_trade_ids(self) -> "ReconciliationRequest":
        trade_ids = [trade.trade_id for trade in self.trades]
        if len(trade_ids) != len(set(trade_ids)):
            raise ValueError("statement trade_id values must be unique")
        return self


class MismatchedTrade(BaseModel):
    trade_id: str
    differing_fields: list[str]


class ReconciliationResponse(BaseModel):
    missing: list[TradeRequest]
    extra: list[TradeResponse]
    mismatched: list[MismatchedTrade]
