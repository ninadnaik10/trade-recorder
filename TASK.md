# Trade Recorder & PnL Service

The task is a Trade Recorder & PnL Service: a backend that ingests trades from multiple venues, tracks positions and reports PnL, with idempotency, reconciliation and an oversell check.

Submit with:
- GitHub repo
- README
- Tests
- DESIGN.md
- AI_USAGE.md

Python with Flask or FastAPI, and Postgres or MySQL, are fine.

## Trade Fields

`venue`, `trade_id`, `symbol`, `side`, `quantity`, `price`, `timestamp`

```json
{
  "venue": "binance",
  "trade_id": "T-1001",
  "symbol": "BTC-USD",
  "side": "BUY",
  "quantity": "10",
  "price": "100",
  "timestamp": "2026-10-30T10:00:00Z"
}
```

## Required

- Ingest with validation
- Idempotency on (venue, trade_id)
- Positions (net quantity and average cost)
- Realized and unrealized PnL from a latest-price endpoint
- An oversell check that leaves the position unchanged
- Reconciliation (missing, extra and mismatched trades)

Use Decimal for money, and state the cost-basis method in DESIGN.md.

## Worked Example

BUY 10 @ 100, BUY 10 @ 110, SELL 5 @ 120, latest price 125:

| | Average cost | FIFO |
|---|---|---|
| Quantity | 15 | 15 |
| Average cost | 105 | 106.67 |
| Realized PnL | 75 | 100 |
| Unrealized PnL | 300 | 275 |

**Oversell:** With a position of 10, a SELL of 15 is rejected and the position stays 10.

**Idempotency:** Sending (binance, T-1001) twice leaves one trade.

**Reconcile:** Stored T1 (10 @ 100) and T2 (5 @ 101). The venue statement shows T1 (10 @ 100), T2 (6 @ 101) and T3 (1 @ 99). Expected: T2 is a quantity mismatch, T3 is missing from your records.