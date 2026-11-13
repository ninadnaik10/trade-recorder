# Trade Recorder & PnL Service

A FastAPI service that ingests trades from multiple venues, tracks positions, and reports realized and unrealized PnL, with idempotent ingestion, an oversell check and venue reconciliation.

See [DESIGN.md](DESIGN.md) for design decisions, including the cost-basis method (average cost), and [AI_USAGE.md](AI_USAGE.md) for how AI tools were used.

## Stack

Python 3.11+, FastAPI, PostgreSQL (SQLAlchemy 2, psycopg 3), Alembic, pytest, [uv](https://docs.astral.sh/uv/).

## Setup

Requires PostgreSQL 14+ running locally. Create the app and test databases:

```bash
createdb trade_recorder
createdb trade_recorder_test
```

Install dependencies and configure the connection:

```bash
uv sync --extra dev
cp .env.example .env   # edit DATABASE_URL and TEST_DATABASE_URL if needed
```

Apply the schema and start the server:

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

The API runs at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

## Tests

```bash
uv run pytest
```

Tests run against the Postgres database in `TEST_DATABASE_URL`. The suite applies the migrations once and empties the tables between tests, so it never touches the app database.

## API

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/trades` | Ingest a trade |
| `GET` | `/trades` | List trades by ingestion order, paginated |
| `GET` | `/trades/{venue}/{trade_id}` | Get one trade |
| `GET` | `/positions` | List positions |
| `GET` | `/positions/{symbol}` | Get one position |
| `PUT` | `/prices/{symbol}` | Set the latest price |
| `GET` | `/prices/{symbol}` | Get the latest price |
| `GET` | `/pnl` | Realized and unrealized PnL for all symbols |
| `GET` | `/pnl/{symbol}` | PnL for one symbol |
| `POST` | `/reconcile/{venue}` | Compare a venue statement with stored trades |

Quantities and prices are sent and returned as decimal strings. Timestamps must include a timezone and are returned in UTC.

### Ingesting trades

```bash
curl -X POST http://localhost:8000/trades \
  -H "Content-Type: application/json" \
  -d '{"venue":"binance","trade_id":"T-1001","symbol":"BTC-USD","side":"BUY","quantity":"10","price":"100","timestamp":"2026-10-30T10:00:00Z"}'
```

| Status | Meaning |
| --- | --- |
| `201 Created` | New trade stored |
| `200 OK` | Identical trade already stored (safe retry); returns the stored trade |
| `409 Conflict`, code `DUPLICATE_CONFLICT` | Same `(venue, trade_id)` with different fields |
| `409 Conflict`, code `OVERSELL` | SELL larger than the current position; nothing is stored |
| `422 Unprocessable Entity` | Validation failed |

### Listing trades

`GET /trades` returns `{"trades": [...], "next_cursor": ...}`, at most `limit` trades (default 100, max 1000). Filter by `venue` and/or `symbol`; both filters can be combined with `limit` and `cursor`. Pass `next_cursor` back as `cursor` to get the next page; it is `null` on the last page.

### Prices and PnL

```bash
curl -X PUT http://localhost:8000/prices/BTC-USD \
  -H "Content-Type: application/json" -d '{"price":"125"}'

curl http://localhost:8000/pnl/BTC-USD
```

If a symbol has no latest price, `latest_price` and `unrealized_pnl` are `null` and realized PnL is still returned.

### Reconciliation

```bash
curl -X POST http://localhost:8000/reconcile/binance \
  -H "Content-Type: application/json" \
  -d '{"trades":[{"venue":"binance","trade_id":"T-1001","symbol":"BTC-USD","side":"BUY","quantity":"10","price":"100","timestamp":"2026-10-30T10:00:00Z"}]}'
```

Every statement trade must belong to the venue in the path. The response lists `missing` trades (on the statement, not stored), `extra` trades (stored, not on the statement), and `mismatched` trades with the stored and statement value of each differing field.

## Project layout

```text
app/
  api/        routes and request/response schemas
  core/       configuration and database setup
  models/     SQLAlchemy models
  services/   business logic
migrations/   Alembic migrations
tests/        API and service tests
```