# Design

## Current state

This repository includes PostgreSQL connection setup, SQLAlchemy models, trade ingestion, price and position reads, PnL reads, and reconciliation.

## Cost basis: average cost

The service will use a moving average-cost method.

- A buy increases quantity and total carrying cost.
- A sell is permitted only when its quantity is no greater than the current position.
- The realized PnL for a sell is `sold_quantity × (sale_price − current_average_cost)`.
- A sell reduces carrying cost by `sold_quantity × current_average_cost`; the average cost of the remaining position stays unchanged.
- Unrealized PnL is `position_quantity × (latest_price − average_cost)`.

For the assignment example, this yields quantity `15`, average cost `105`, realized PnL `75`, and unrealized PnL `300` at a latest price of `125`.

## Intended ownership

| Layer | Responsibility |
| --- | --- |
| API | Parse requests, return response models and HTTP errors |
| Models | Persist trades, positions, latest prices, and statement records |
| Services | Apply validation, idempotency, oversell, cost-basis, PnL, and reconciliation rules |
| Database transaction | Atomically insert an accepted trade and update its position |

## Data and integrity plan

- Quantities, prices, costs, and PnL use PostgreSQL `NUMERIC(38, 18)` columns and Python `Decimal` values.
- The trade request model accepts quantity and price only as nonempty strings, then parses them directly to `Decimal`; numeric JSON values and floats are rejected.
- The trade request model requires a timezone-aware ISO 8601 timestamp, nonempty identifying fields, and an exact `BUY` or `SELL` side.
- Enforce a unique constraint on `(venue, trade_id)`.
- Trade ingestion uses one transaction to check idempotency, create a zero position with `INSERT ... ON CONFLICT DO NOTHING`, lock the position row, update the position, and insert the trade. A rejected oversell rolls back the entire transaction.
- Latest-price writes use `INSERT ... ON CONFLICT DO UPDATE`, so concurrent first writes for a symbol cannot fail on the primary key.
- The application creates the initial tables at startup for a fresh local database. Introduce versioned migrations before changing an existing schema.
- PnL reads use an outer join between positions and latest prices. A missing price leaves `latest_price` and unrealized PnL as `null`, while realized PnL remains available. A one-symbol request returns `404` only when its position is unavailable.
- Treat a repeated submission with the same unique key as idempotent only if its immutable trade fields match; a conflicting payload will return a conflict error.
- Reconciliation compares normalized statement records to stored records by `(venue, trade_id)`, then classifies them as missing, extra, or mismatched. Matching IDs compare symbol, side, quantity, price, and timestamp.

## Test coverage

Tests cover malformed input, duplicate ingestion, the provided PnL example, oversell rejection without mutation, and missing/mismatched reconciliation cases.

