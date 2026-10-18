# Order Service

## Local development

Run from `order-service/`:

```sh
uv sync
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 3002
```

The service creates its tables from ORM metadata on startup.

## Order and credit state

Orders expose business progress in `status` and the current financial operation's
outcome in `credit_status` (`pending`, `succeeded`, or `rejected`).

| Order status | Credit operation |
| --- | --- |
| `init`, `rejected` | Reserve |
| `open`, `accepted`, `picked_up`, `delivered` | Successful reserve remains held |
| `disputed` | Held reserve for fulfilment disputes; transfer outcome for settlement disputes |
| `cancelled`, `expired` | Release (initialization expiry first awaits the reservation outcome) |
| `received`, `completed` | Transfer |

Creation starts at `(init, pending)`. Reservation success opens the order;
rejection produces `(rejected, rejected)`. Cancellation or expiry queues a release;
receipt confirmation queues a transfer, setting credit status to `pending`.
Transfer success completes the order; rejection leaves `(received, rejected)`.
Release results never reopen cancelled or expired orders.

Missing replies trigger command replay. Explicit rejections are terminal outcomes,
not automatically retried. `status_reason` explains expiry or dispute, including
initialization failures where no credits were reserved and no refund is needed.

## Creation idempotency

`POST /orders` requires an `Idempotency-Key` header (1–128 characters, not blank).
Use a new UUID for each new order and reuse it when retrying the same submission.
Keys are scoped to the requester and stored atomically with the order and reservation
command. Identical retries return the current order with 202 without calling Supplier;
a changed request with the same key returns 409. Supplier snapshots are excluded from
comparison. Creation uses PostgreSQL's default READ COMMITTED isolation.

## Deadlines and disputes

Deadlines use PostgreSQL's clock:

| Setting | Default | On timeout |
| --- | --- | --- |
| `ORDER_INIT_TIMEOUT_SECONDS` | 60 | Expire unconfirmed reservations |
| `ORDER_OPEN_TIMEOUT_SECONDS` | 900 | Expire open orders and release credits |
| `ORDER_PROGRESS_TIMEOUT_SECONDS` | 900 | Dispute stalled pickup, delivery, or receipt |
| `ORDER_SETTLEMENT_TIMEOUT_SECONDS` | 900 | Dispute unresolved transfers |

Reservation replay continues after initialization expiry: delayed success queues
one release; rejection records that no credits were reserved. Transfer replay
continues after settlement timeout, updating credit status without leaving dispute.
A transfer rejection before the deadline remains `(received, rejected)` until disputed.

Each of `accepted`, `picked_up`, and `delivered` starts a fresh `progress_due_at`.
Receipt clears it and starts `settlement_due_at`. The worker sweeps every 10 seconds;
forward transitions also check deadlines after locking the order.

The requester or assigned courier can call `PATCH /orders/{order_id}/dispute` with
`{"reason": "Supplier closed"}` from `accepted`, `picked_up`, `delivered`, or
`(received, rejected)`. Reasons must contain 1–2000 characters after trimming.
Outsiders receive 403; ineligible states receive 409. Retries preserve the first reason.

Disputes permanently freeze business progress without queuing financial commands.
Fulfilment disputes retain reserved credits; settlement disputes record eventual
payment outcomes. Resolution workflows are not implemented.

For countdowns, authenticated `GET /orders/clock` returns `server_time`. Count down
against `expires_at` or `progress_due_at` using elapsed monotonic browser time;
resync on focus/reconnect and refetch state at zero. Poll lists for status updates.

## Tests

```sh
PYTHONPATH=src uv run python -m unittest discover -s tests
```

Set `ORDER_TEST_DATABASE_URL` to a PostgreSQL SQLAlchemy URL to run the four
regressions covering concurrent creation, replay conflicts, late refunds, and
late settlement. Tests use isolated temporary schemas.

## Docker Compose

Run from the repository root:

```sh
docker compose up --build user-service order-service
```
