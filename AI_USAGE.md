# AI Usage

I used AI coding assistants mainly for boilerplate and test generation. Design decisions, review and verification were mine.

## Boilerplate

AI generated the initial project scaffold: the FastAPI app and router setup, SQLAlchemy models, Pydantic request and response schemas, database session handling, settings, and the Alembic configuration. I reviewed this code and changed it where it was wrong or didn't fit the design. For example, I removed table creation at application startup, because it conflicted with the Alembic migrations and made `alembic upgrade head` fail on a fresh database.

## Tests

AI generated most of the test code from scenarios I specified: the worked PnL example, idempotency, oversell, validation cases, pagination and reconciliation, along with the exact expected values for each. I checked those expected values by hand against the assignment's examples rather than trusting the generated assertions.

Review of the first generated tests found that they ran on SQLite, which stores `NUMERIC` as a float, so they could not prove exact decimal handling. A price of `100.123456789012345678` came back as `100.123456789012351464`. I moved the tests to PostgreSQL and added HTTP-level tests that check status codes and response bodies, not just service functions.

## Review and verification

I used AI to review the code before submission. It flagged issues that I then confirmed and fixed, including a race where two concurrent first trades on a new symbol could fail with a 500, and PnL returning 404 instead of realized PnL when no latest price was set.

Beyond the automated tests, I verified the service by running the migrations against a local PostgreSQL database and exercising every endpoint with `curl`, comparing the responses with the expected results.