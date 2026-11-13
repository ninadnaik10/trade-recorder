
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.schemas import TradeRequest
from app.services.errors import OversellError
from app.services.pnl import get_pnl, list_pnl
from app.services.positions import get_position
from app.services.prices import set_latest_price
from app.services.reconciliation import StatementTrade, reconcile
from app.services.trade_ingestion import ingest_trade
from app.services.trade_queries import list_trades_page


def trade_payload(
    trade_id: str = "T-1001",
    side: str = "BUY",
    quantity: str = "10",
    price: str = "100",
) -> dict[str, object]:
    return {
        "venue": "binance",
        "trade_id": trade_id,
        "symbol": "BTC-USD",
        "side": side,
        "quantity": quantity,
        "price": price,
        "timestamp": "2026-10-30T10:00:00Z",
    }


def make_trade(**overrides: str) -> TradeRequest:
    return TradeRequest.model_validate(trade_payload(**overrides))


def ingest(session: Session, **overrides: str):
    return ingest_trade(session, **make_trade(**overrides).model_dump())


def test_pnl_worked_example(session: Session) -> None:
    ingest(session, trade_id="T-1", quantity="10", price="100")
    ingest(session, trade_id="T-2", quantity="10", price="110")
    ingest(session, trade_id="T-3", side="SELL", quantity="5", price="120")
    set_latest_price(session, "BTC-USD", Decimal(125))

    pnl = get_pnl(session, "BTC-USD")

    assert pnl.quantity == Decimal(15)
    assert pnl.average_cost == Decimal(105)
    assert pnl.realized_pnl == Decimal(75)
    assert pnl.unrealized_pnl == Decimal(300)
    assert list_pnl(session) == [pnl]


def test_pnl_keeps_realized_value_without_a_latest_price(session: Session) -> None:
    ingest(session, trade_id="T-1", quantity="10", price="100")
    ingest(session, trade_id="T-2", side="SELL", quantity="5", price="120")

    pnl = get_pnl(session, "BTC-USD")

    assert pnl.quantity == Decimal(5)
    assert pnl.realized_pnl == Decimal(100)
    assert pnl.latest_price is None
    assert pnl.unrealized_pnl is None
    assert list_pnl(session) == [pnl]


def test_latest_price_upsert_replaces_the_existing_price(session: Session) -> None:
    ingest(session)
    set_latest_price(session, "BTC-USD", Decimal(100))
    set_latest_price(session, "BTC-USD", Decimal(125))

    pnl = get_pnl(session, "BTC-USD")

    assert pnl.latest_price == Decimal(125)
    assert pnl.unrealized_pnl == Decimal(250)


def test_oversell_is_rejected_without_changing_position(session: Session) -> None:
    ingest(session, quantity="10")

    with pytest.raises(OversellError):
        ingest(session, trade_id="T-1002", side="SELL", quantity="15")

    assert get_position(session, "BTC-USD").quantity == Decimal(10)
    trades, _ = list_trades_page(session, limit=10)
    assert len(trades) == 1


def test_duplicate_trade_is_idempotent(session: Session) -> None:
    first = ingest(session)
    second = ingest(session)

    assert first.created is True
    assert second.created is False
    trades, _ = list_trades_page(session, limit=10)
    assert len(trades) == 1
    assert trades[0].venue == "binance"
    assert trades[0].trade_id == "T-1001"


def test_trade_listing_uses_id_cursor_pagination(session: Session) -> None:
    ingest(session, trade_id="T-1")
    ingest(session, trade_id="T-2")
    ingest(session, trade_id="T-3")

    first_page, next_cursor = list_trades_page(session, limit=2)
    second_page, final_cursor = list_trades_page(session, limit=2, cursor=next_cursor)

    assert [trade.trade_id for trade in first_page] == ["T-1", "T-2"]
    assert next_cursor == first_page[-1].id
    assert [trade.trade_id for trade in second_page] == ["T-3"]
    assert final_cursor is None


def test_reconciliation_reports_missing_and_mismatched_trades(session: Session) -> None:
    ingest(session, trade_id="T1", quantity="10", price="100")
    ingest(session, trade_id="T2", quantity="5", price="101")
    result = reconcile(
        session,
        "binance",
        [
            to_statement(make_trade(trade_id="T1", quantity="10", price="100")),
            to_statement(make_trade(trade_id="T2", quantity="6", price="101")),
            to_statement(make_trade(trade_id="T3", quantity="1", price="99")),
        ],
    )

    assert [trade.trade_id for trade in result.missing] == ["T3"]
    assert result.extra == []
    assert [(item.trade_id, item.differences) for item in result.mismatched] == [
        ("T2", {"quantity": (Decimal(5), Decimal(6))})
    ]


def test_reconciliation_reports_extra_trades(session: Session) -> None:
    ingest(session, trade_id="T4")

    result = reconcile(session, "binance", [])

    assert [trade.trade_id for trade in result.extra] == ["T4"]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("venue", ""),
        ("side", "HOLD"),
        ("quantity", "0"),
        ("quantity", "-1"),
        ("quantity", 10),
        ("price", "0"),
        ("price", "not-a-decimal"),
        ("timestamp", "not-a-timestamp"),
        ("timestamp", "2026-10-30T10:00:00"),
    ],
)
def test_malformed_trade_is_rejected(
    field: str, value: object
) -> None:
    payload = trade_payload()
    payload[field] = value

    with pytest.raises(ValidationError):
        TradeRequest.model_validate(payload)


def test_trade_with_missing_required_field_is_rejected() -> None:
    payload = trade_payload()
    del payload["trade_id"]

    with pytest.raises(ValidationError):
        TradeRequest.model_validate(payload)


def to_statement(trade: TradeRequest) -> StatementTrade:
    return StatementTrade(**trade.model_dump())
