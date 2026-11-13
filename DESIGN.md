# Design

## Overview

FastAPI service backed by PostgreSQL. Routes in `app/api` parse requests and map errors to HTTP responses; business rules live in `app/services`; SQLAlchemy models live in `app/models`. The schema is managed by Alembic migrations.

## Cost basis: average cost

Positions use the moving average-cost method:

- A BUY updates the average: `(old_qty × old_avg + qty × price) / (old_qty + qty)`.
- A SELL books realized PnL of `qty × (price − avg)` and reduces quantity; the average is unchanged.
- When a position returns to zero, its average cost resets to zero.
- Unrealized PnL is `qty × (latest_price − avg)`.

For the worked example this gives quantity 15, average cost 105, realized PnL 75 and unrealized PnL 300.

Average cost was chosen because the task already requires an average-cost field on positions, and it needs only two numbers per symbol. FIFO would be preferred where tax or audit rules require lot-level tracking; it could be added with a `lots` table consumed oldest-first on each SELL.

## Money and time

- Quantities, prices and PnL are `NUMERIC(38, 18)` in Postgres and `Decimal` in Python. Floats are never used, because binary floating point cannot represent most decimals exactly, and idempotency and reconciliation depend on exact equality.
- The API accepts quantity and price only as JSON strings, so values are parsed straight to `Decimal`. Responses return normalized decimal strings (`"105"`, not `"105.000000000000000000"`).
- Timestamps must include a timezone. They are stored as `TIMESTAMPTZ` and returned in UTC.

## Ingestion, idempotency and oversell

`(venue, trade_id)` is the idempotency key, enforced by a unique constraint. Each ingestion runs in one transaction:

1. Look up an existing trade with the same key. If its fields match, return it with `200 OK`; if they differ, return `409` with code `DUPLICATE_CONFLICT`.
2. Ensure the symbol's position row exists (`INSERT … ON CONFLICT DO NOTHING`), then lock it with `SELECT … FOR UPDATE`, so concurrent trades on one symbol are serialized.
3. For a SELL larger than the position, raise an oversell error. The whole transaction rolls back, so neither the trade nor the position changes, and the client gets `409` with code `OVERSELL`.
4. Update the position and insert the trade, then commit.

If two identical requests race past step 1, the unique constraint rejects the second insert, and the service returns the stored trade instead.

## PnL and prices

`PUT /prices/{symbol}` upserts the latest price. PnL reads outer-join positions with prices: when no price exists, `latest_price` and `unrealized_pnl` are `null`, while realized PnL is still returned.

## Reconciliation

`POST /reconcile/{venue}` compares a venue statement with stored trades for that venue, keyed by `trade_id`:

- **missing**: on the statement, not stored
- **extra**: stored, not on the statement
- **mismatched**: on both, with the stored and statement values of each differing field (symbol, side, quantity, price, timestamp)

Reconciliation only reports differences; it never changes stored trades.

## Pagination

`GET /trades` uses keyset pagination on `id` (`limit` and `cursor`). Unlike offset pagination, it does not skip or repeat rows when trades arrive between page requests, and stays fast on large tables.

## Limitations

- **Arrival order.** Trades are applied in the order they arrive, not by `timestamp`. A SELL that arrives before its BUY is rejected, and a late trade changes the average used by later sells. A production system would rebuild positions from trades sorted by timestamp.
- **Cross-venue positions.** Positions aggregate a symbol across all venues.
- **Reconciliation scope.** A statement is compared with every stored trade for the venue, so a statement covering one day reports older trades as extra. A date-range filter would fix this. Rejected oversells are not stored, so they appear as missing.
- **Symbols are case-sensitive.** `btc-usd` and `BTC-USD` are separate positions.