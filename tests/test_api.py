import pytest
from fastapi.testclient import TestClient


def trade_payload(
    trade_id: str = "T-1001",
    venue: str = "binance",
    symbol: str = "BTC-USD",
    side: str = "BUY",
    quantity: str | int = "10",
    price: str = "100",
    timestamp: str = "2026-10-30T10:00:00Z",
) -> dict[str, object]:
    return {
        "venue": venue,
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "timestamp": timestamp,
    }


def post_trade(client: TestClient, **overrides: object):
    return client.post("/trades", json=trade_payload(**overrides))


def test_trade_responses_are_consistent_and_normalized(client: TestClient) -> None:
    payload = trade_payload(quantity="10.00", price="100.000000000000000000")
    created = client.post("/trades", json=payload)
    resent = client.post("/trades", json=payload)
    fetched = client.get("/trades/binance/T-1001")
    listed = client.get("/trades?limit=10")
    reconciled = client.post("/reconcile/binance", json={"trades": []})

    assert created.status_code == 201
    assert resent.status_code == 200
    assert created.json() == {
        "venue": "binance",
        "trade_id": "T-1001",
        "symbol": "BTC-USD",
        "side": "BUY",
        "quantity": "10",
        "price": "100",
        "timestamp": "2026-10-30T10:00:00Z",
    }
    assert resent.json() == created.json()
    assert fetched.json() == created.json()
    assert listed.json() == {"trades": [created.json()], "next_cursor": None}
    assert reconciled.json()["extra"] == [created.json()]


def test_idempotency_and_conflict_errors(client: TestClient) -> None:
    assert post_trade(client).status_code == 201
    assert post_trade(client).status_code == 200
    assert post_trade(client, quantity="10.00").status_code == 200

    conflict = post_trade(client, quantity="11")
    other_venue = post_trade(client, venue="kraken")

    assert conflict.status_code == 409
    assert conflict.json() == {
        "detail": {
            "code": "DUPLICATE_CONFLICT",
            "message": "venue and trade_id already identify a different trade",
        }
    }
    assert other_venue.status_code == 201
    assert client.get("/trades?limit=10").json()["trades"] == [
        post_trade(client).json(),
        other_venue.json(),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        {key: value for key, value in trade_payload().items() if key != "price"},
        trade_payload(side="HOLD"),
        trade_payload(quantity="0"),
        trade_payload(quantity="-1"),
        trade_payload(quantity=10),
        trade_payload(price="abc"),
        trade_payload(timestamp="2026-10-30T10:00:00"),
    ],
)
def test_invalid_trade_payloads_return_422(client: TestClient, payload: dict[str, object]) -> None:
    assert client.post("/trades", json=payload).status_code == 422


def test_malformed_json_returns_422(client: TestClient) -> None:
    response = client.post(
        "/trades",
        content='{"venue":"binance",',
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


def test_worked_example(client: TestClient) -> None:
    assert post_trade(client, trade_id="T-1", quantity="10", price="100").status_code == 201
    assert post_trade(client, trade_id="T-2", quantity="10", price="110").status_code == 201
    assert post_trade(client, trade_id="T-3", side="SELL", quantity="5", price="120").status_code == 201
    assert client.put("/prices/BTC-USD", json={"price": "125"}).status_code == 200

    assert client.get("/positions/BTC-USD").json() == {
        "symbol": "BTC-USD",
        "quantity": "15",
        "average_cost": "105",
    }
    assert client.get("/pnl/BTC-USD").json() == {
        "symbol": "BTC-USD",
        "quantity": "15",
        "average_cost": "105",
        "latest_price": "125",
        "realized_pnl": "75",
        "unrealized_pnl": "300",
    }


def test_oversell_conflict_does_not_change_position(client: TestClient) -> None:
    assert post_trade(client, trade_id="BUY-1").status_code == 201
    response = post_trade(client, trade_id="SELL-1", side="SELL", quantity="15")

    assert response.status_code == 409
    assert response.json() == {
        "detail": {
            "code": "OVERSELL",
            "message": "sell quantity exceeds the current position",
        }
    }
    assert client.get("/positions/BTC-USD").json() == {
        "symbol": "BTC-USD",
        "quantity": "10",
        "average_cost": "100",
    }
    assert client.get("/pnl/BTC-USD").json()["realized_pnl"] == "0"
    assert client.get("/trades/binance/SELL-1").status_code == 404


def test_oversell_without_position_returns_409(client: TestClient) -> None:
    response = post_trade(client, symbol="DOGE-USD", side="SELL", quantity="1")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "OVERSELL"
    assert client.get("/positions/DOGE-USD").status_code == 404


def test_zero_position_resets_average_cost(client: TestClient) -> None:
    assert post_trade(client, trade_id="B-1", quantity="10", price="100").status_code == 201
    assert post_trade(client, trade_id="S-1", side="SELL", quantity="10", price="120").status_code == 201
    assert post_trade(client, trade_id="B-2", quantity="2", price="150").status_code == 201

    assert client.get("/positions/BTC-USD").json()["average_cost"] == "150"


def test_pnl_without_latest_price_is_listed(client: TestClient) -> None:
    assert post_trade(client, quantity="5", price="100").status_code == 201

    response = client.get("/pnl/BTC-USD")
    listed = client.get("/pnl")

    assert response.status_code == 200
    assert response.json() == {
        "symbol": "BTC-USD",
        "quantity": "5",
        "average_cost": "100",
        "latest_price": None,
        "realized_pnl": "0",
        "unrealized_pnl": None,
    }
    assert listed.json() == [response.json()]


@pytest.mark.parametrize(
    "path",
    [
        "/positions/UNKNOWN",
        "/pnl/UNKNOWN",
        "/prices/UNKNOWN",
        "/trades/binance/UNKNOWN",
    ],
)
def test_unknown_resources_return_404(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


def test_prices_upsert_and_validate(client: TestClient) -> None:
    first = client.put("/prices/BTC-USD", json={"price": "100"})
    second = client.put("/prices/BTC-USD", json={"price": "125"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert client.get("/prices/BTC-USD").json()["price"] == "125"
    assert client.put("/prices/BTC-USD", json={"price": "0"}).status_code == 422
    assert client.put("/prices/BTC-USD", json={"price": "-5"}).status_code == 422


def test_trade_pagination(client: TestClient) -> None:
    for index in range(5):
        assert post_trade(client, trade_id=f"T-{index}").status_code == 201

    pages = []
    cursor = None
    while True:
        params = {"limit": 2}
        if cursor is not None:
            params["cursor"] = cursor
        response = client.get("/trades", params=params)
        assert response.status_code == 200
        body = response.json()
        pages.append(body["trades"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert [len(page) for page in pages] == [2, 2, 1]
    assert [trade["trade_id"] for page in pages for trade in page] == [f"T-{i}" for i in range(5)]


@pytest.mark.parametrize("limit", [0, 1001])
def test_trade_pagination_limit_validation(client: TestClient, limit: int) -> None:
    assert client.get("/trades", params={"limit": limit}).status_code == 422


def test_trade_filters_and_filtered_pagination(client: TestClient) -> None:
    trades = [
        {"trade_id": "T-1", "venue": "binance", "symbol": "BTC-USD"},
        {"trade_id": "T-2", "venue": "kraken", "symbol": "BTC-USD"},
        {"trade_id": "T-3", "venue": "binance", "symbol": "ETH-USD"},
        {"trade_id": "T-4", "venue": "kraken", "symbol": "ETH-USD"},
        {"trade_id": "T-5", "venue": "binance", "symbol": "BTC-USD"},
    ]
    for trade in trades:
        assert post_trade(client, **trade).status_code == 201

    assert [trade["trade_id"] for trade in client.get("/trades?venue=binance").json()["trades"]] == [
        "T-1",
        "T-3",
        "T-5",
    ]
    assert [trade["trade_id"] for trade in client.get("/trades?symbol=BTC-USD").json()["trades"]] == [
        "T-1",
        "T-2",
        "T-5",
    ]
    assert [
        trade["trade_id"]
        for trade in client.get("/trades?venue=binance&symbol=BTC-USD").json()["trades"]
    ] == ["T-1", "T-5"]
    assert client.get("/trades?venue=unknown").json() == {
        "trades": [],
        "next_cursor": None,
    }
    assert client.get("/trades?venue=").status_code == 422
    assert client.get("/trades?symbol=").status_code == 422

    pages = []
    cursor = None
    while True:
        params = {"venue": "binance", "limit": 1}
        if cursor is not None:
            params["cursor"] = cursor
        body = client.get("/trades", params=params).json()
        pages.extend(body["trades"])
        cursor = body["next_cursor"]
        if cursor is None:
            break

    assert [trade["trade_id"] for trade in pages] == ["T-1", "T-3", "T-5"]


def test_reconciliation_reports_value_differences(client: TestClient) -> None:
    assert post_trade(client, trade_id="T1", quantity="10", price="100").status_code == 201
    assert post_trade(client, trade_id="T2", quantity="5", price="101").status_code == 201
    statement = {
        "trades": [
            trade_payload(trade_id="T1", quantity="10", price="100"),
            trade_payload(trade_id="T2", quantity="6", price="101"),
            trade_payload(trade_id="T3", quantity="1", price="99"),
        ]
    }

    response = client.post("/reconcile/binance", json=statement)

    assert response.status_code == 200
    assert response.json()["missing"][0]["trade_id"] == "T3"
    assert response.json()["extra"] == []
    assert response.json()["mismatched"] == [
        {"trade_id": "T2", "differences": {"quantity": {"stored": "5", "statement": "6"}}}
    ]


def test_reconciliation_reports_extra_and_multiple_differences(client: TestClient) -> None:
    stored = post_trade(client, trade_id="T1").json()
    assert post_trade(client, trade_id="T2", symbol="ETH-USD").status_code == 201
    statement = {
        "trades": [
            trade_payload(
                trade_id="T1",
                symbol="ETH-USD",
                side="SELL",
                quantity="11",
                price="101",
            )
        ]
    }

    response = client.post("/reconcile/binance", json=statement)

    assert response.status_code == 200
    assert response.json()["missing"] == []
    assert response.json()["extra"] == [post_trade(client, trade_id="T2", symbol="ETH-USD").json()]
    assert response.json()["mismatched"] == [
        {
            "trade_id": "T1",
            "differences": {
                "symbol": {"stored": "BTC-USD", "statement": "ETH-USD"},
                "side": {"stored": "BUY", "statement": "SELL"},
                "quantity": {"stored": "10", "statement": "11"},
                "price": {"stored": "100", "statement": "101"},
            },
        }
    ]
    assert client.get("/trades/binance/T1").json() == stored


def test_reconciliation_validates_venue_and_duplicate_ids(client: TestClient) -> None:
    statement = trade_payload()
    statement["venue"] = "kraken"
    assert client.post("/reconcile/binance", json={"trades": [statement]}).status_code == 422

    duplicate = trade_payload()
    assert (
        client.post("/reconcile/binance", json={"trades": [duplicate, duplicate]}).status_code == 422
    )


def test_other_venue_is_ignored_by_reconciliation(client: TestClient) -> None:
    assert post_trade(client, venue="kraken").status_code == 201

    response = client.post("/reconcile/binance", json={"trades": []})

    assert response.status_code == 200
    assert response.json()["extra"] == []


def test_decimal_precision_round_trips(client: TestClient) -> None:
    price = "100.123456789012345678"
    assert post_trade(client, price=price).json()["price"] == price
    assert client.get("/trades/binance/T-1001").json()["price"] == price
