from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    Field,
    PlainSerializer,
    StringConstraints,
    field_validator,
    model_validator,
)

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
PositiveDecimalString = Annotated[
    Decimal,
    Field(gt=Decimal(0), max_digits=38, decimal_places=18),
]


def _format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


DecimalStr = Annotated[
    Decimal,
    PlainSerializer(_format_decimal, return_type=str, when_used="json"),
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
        return value.astimezone(UTC)


class TradeResponse(BaseModel):
    venue: str
    trade_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: DecimalStr
    price: DecimalStr
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class TradePageResponse(BaseModel):
    trades: list[TradeResponse]
    next_cursor: int | None


class PositionResponse(BaseModel):
    symbol: str
    quantity: DecimalStr
    average_cost: DecimalStr


class LatestPriceRequest(BaseModel):
    price: PositiveDecimalString

    @field_validator("price", mode="before")
    @classmethod
    def require_decimal_string(cls, value: object) -> str:
        return _require_decimal_string(value)


class LatestPriceResponse(BaseModel):
    symbol: str
    price: DecimalStr
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return value.astimezone(UTC)


class PnlResponse(BaseModel):
    symbol: str
    quantity: DecimalStr
    average_cost: DecimalStr
    latest_price: DecimalStr | None
    realized_pnl: DecimalStr
    unrealized_pnl: DecimalStr | None


class ReconciliationRequest(BaseModel):
    trades: list[TradeRequest]

    @model_validator(mode="after")
    def require_unique_trade_ids(self) -> "ReconciliationRequest":
        trade_ids = [trade.trade_id for trade in self.trades]
        if len(trade_ids) != len(set(trade_ids)):
            raise ValueError("statement trade_id values must be unique")
        return self


class MismatchValues(BaseModel):
    stored: str
    statement: str


class MismatchedTrade(BaseModel):
    trade_id: str
    differences: dict[str, MismatchValues]


class ReconciliationResponse(BaseModel):
    missing: list[TradeResponse]
    extra: list[TradeResponse]
    mismatched: list[MismatchedTrade]
