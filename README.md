# Trade Recorder & PnL Service

FastAPI service for the Brown Rice Capital take-home assignment. It supports validated trade ingestion and PnL reporting from stored positions and latest prices.

## Stack

- Python 3.11+
- FastAPI
- PostgreSQL, via SQLAlchemy and psycopg
- Pytest for tests

## Setup

Create and activate a virtual environment, then install the development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Copy the database configuration template and change it for your local PostgreSQL instance:

```bash
cp .env.example .env
```

Run the application with:

```bash
uvicorn app.main:app --reload
```

On startup, the application creates the `trades`, `positions`, and `market_prices` tables if they do not exist.

Run the test suite with:

```bash
uv run pytest
```

## API routes

| Method | Path | Responsibility |
| --- | --- | --- |
| `POST` | `/trades` | Ingest a trade |
| `GET` | `/trades` | List stored trades in timestamp order |
| `GET` | `/trades/{venue}/{trade_id}` | Return one trade by its idempotency key |
| `GET` | `/positions` | List positions |
| `GET` | `/positions/{symbol}` | Return a position |
| `GET` | `/prices/{symbol}` | Return the latest price |
| `PUT` | `/prices/{symbol}` | Set the latest price |
| `GET` | `/pnl` | List PnL by symbol |
| `GET` | `/pnl/{symbol}` | Return PnL for a symbol |
| `POST` | `/reconcile/{venue}` | Reconcile a venue statement |

The routes are registered and documented at `/docs`. All routes are implemented.

`POST /trades` already validates request shape. It requires nonempty `venue`, `trade_id`, and `symbol` strings; an exact `BUY` or `SELL` side; positive quantity and price decimal strings; and a timezone-aware ISO 8601 timestamp. Invalid submissions receive FastAPI's `422` validation response.

An accepted new trade returns `201 Created`. Resubmitting the same trade returns the stored trade with `200 OK`; a reused `(venue, trade_id)` with different fields returns `409 Conflict`. An oversell also returns `409 Conflict` and rolls back the transaction.

`GET /trades` returns all stored trades ordered by timestamp. `GET /trades/{venue}/{trade_id}` returns `404 Not Found` when that idempotency key does not exist.

`GET /positions` returns positions ordered by symbol. `GET /positions/{symbol}` returns `404 Not Found` when the symbol has no stored position.

`PUT /prices/{symbol}` creates or replaces the latest price. Its `price` field must be a positive decimal string. `GET /prices/{symbol}` returns `404 Not Found` when no latest price exists.

`GET /pnl` returns every stored position, including positions without a latest price. `GET /pnl/{symbol}` returns `404 Not Found` only when the position is unavailable. When a price is missing, `latest_price` and `unrealized_pnl` are `null`; realized PnL remains available. Unrealized PnL is `quantity × (latest_price − average_cost)` when a price exists.

`POST /reconcile/{venue}` accepts `{ "trades": [...] }`, where every trade belongs to the path venue. It returns statement records missing from storage, stored records extra to the statement, and each matching `trade_id` with its differing fields.

## Project layout

```text
app/
  api/       HTTP routes
  core/      configuration and infrastructure
  models/    SQLAlchemy persistence models
  services/  domain logic
tests/       acceptance and unit tests
```

See [DESIGN.md](DESIGN.md) for the selected cost-basis method and implementation plan.

