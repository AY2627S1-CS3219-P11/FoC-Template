# Credit Service

## Requirements

- Python 3.14 or newer
- `uv`
- A running RabbitMQ broker
- A running User Service reachable through the internal gateway

## Install

Run from `credit-service/`:

```sh
uv sync
```

Set `DATABASE_URL`, `RABBITMQ_URL`, and `INTERNAL_GATEWAY_URL` in `.env` using
`.env.example` as a reference. `INITIAL_CREDIT_ALLOCATION` defaults to `100`.

## Development

For a local Docker broker, use `localhost` as the hostname in `RABBITMQ_URL`.
Set `INTERNAL_GATEWAY_URL` to a reachable gateway origin; the Docker gateway
hostname is available only inside the Compose network.

```sh
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 3002
```

Open <http://127.0.0.1:3002/docs>.

## Docker Compose

Use `rabbitmq` as the hostname in `RABBITMQ_URL`. Run from the repository root:

```sh
docker compose up --build user-service credit-service
```

Open <http://localhost:3002/docs>.

## Database choice and credit model

Credit uses its own PostgreSQL database, hosted on Neon in the current
deployment. The model supports wallet lookups by user ID, reservation lookups
by order ID, active reservations for a user, and credit-operation records.
PostgreSQL primary keys, foreign keys, check constraints, transactions, and row
locks support these queries and
concurrent credit updates.

| Table | Stored fields | Purpose |
| --- | --- | --- |
| `credits` | `user_id` (primary key), `available_credits`, `reserved_credits`, `created_at`, `updated_at` | One wallet per user |
| `credit_reservations` | `order_id` (primary key), `user_id`, `amount`, `status`, `created_at`, `updated_at` | One reservation per order, including its final status |
| `credit_audit_logs` | `log_id` (primary key), `user_id`, optional `recipient_user_id` and `order_id`, `action`, `amount`, `created_at` | Existing schema for initial allocation, reservation, release, and transfer records |

The operation-record schema already exists; audit writes remain deferred.

Reservation amounts must be positive, and statuses are `RESERVED`, `RELEASED`,
or `TRANSFERRED`. Each reservation references a wallet in the local `credits`
table. User and Order identifiers refer to other services logically; there are
no foreign keys into their databases. The `(user_id, status)` index supports
queries for a user's active reservations. Startup creates the new table through
the existing metadata initialization and preserves existing wallets.

Available and reserved balances are stored as nonnegative integers. The ORM's
`total_credits` property calculates `available_credits + reserved_credits` from
the stored balances; there is no separately stored total to synchronize. The current
balance API continues to return only available and reserved credits.
Only available credits can fund a new reservation. Total includes credits
already held for other orders and must not be used as the spending limit.

The reservation invariant is that each wallet's reserved balance equals the
sum of its `RESERVED` reservation amounts. For example, reserving 30 credits
moves a wallet from `100 / 0` to `70 / 30` and creates a 30-credit reservation
for that order. Released or transferred reservations remain in the table and
no longer contribute to the reserved sum.

Reservation, release, and transfer operations belong to D3 point 3 and are not
implemented yet. Those operations must update the wallet and reservation in
one Credit database transaction, locking the affected wallets before checking
and changing balances. This enforces the aggregate invariant and prevents
concurrent orders from reserving the same credits. The schema checks individual
rows; it does not enforce the reserved sum across tables by itself. Credit
operations preserve the global sum of available and reserved credits;
initial allocation intentionally increases it when a new wallet is created.

## Current balance

`GET /credits/current` returns only `available_credits` and `reserved_credits`
from the authenticated user's stored balance. Through the UI/gateway, use
`GET /credit-api/credits/current`. Swagger accepts an access token through
**Authorize**; requests without an Authorization header use the `access_token`
cookie. An explicitly supplied invalid token is rejected.
Missing or invalid tokens return `401`, unavailable verification returns `503`,
and an account still awaiting initialization returns `404`.

## Initial allocation and existing accounts

The team allocation is **100 available credits and 0 reserved credits**,
configured by `INITIAL_CREDIT_ALLOCATION` with a default of `100`. A new account
can fund multiple errands before earning credits as a courier: for illustration,
100 credits would fund 20 errands priced at 5 credits each. This illustrates the
allocation's scale; the number of affordable errands depends on their rewards.
For Compose, set `INITIAL_CREDIT_ALLOCATION` in the root environment or root
`.env`; Compose supplies that value to Credit. Running Credit directly reads
the setting from its service environment or `credit-service/.env`.

New registrations save a `UserCreated` event in User Service's outbox in the
same transaction as the account. The publisher retries until RabbitMQ confirms
persistent delivery. Credit commits the configured allocation before
acknowledging; a repeated user ID leaves existing balances and timestamps intact.

If publication fails, the outbox retains the event for retry. If Credit is
offline, the durable queue holds it; if Credit's database write fails, the
consumer requeues it. Registration can succeed while allocation is pending,
and the balance endpoint returns `404` until the wallet exists. Allocation
becomes visible after recovery. The wallet's unique `user_id` and
`ON CONFLICT DO NOTHING` prevent duplicate events from granting credits again,
including a redelivery after a commit whose acknowledgement was interrupted.

Each Credit startup requests reconciliation through a durable RabbitMQ queue.
User Service queues its existing account IDs and original creation times through
the same outbox. Missing Credit accounts receive the configured available
balance and zero reserved credits asynchronously. Existing accounts are never
reset. Changing the allocation affects only accounts initialized afterward.

Both services declare the same durable direct exchange, `user_events`.
User publishes `UserCreated` with the routing key `user.created`; Credit consumes
it from `credit_user_created`. Credit publishes `CreditAccountsSyncRequested`
with the routing key `credit.accounts.sync.requested`; User consumes it from
`credit_accounts_sync_requested`, queries its own users table, and queues their
`UserCreated` events for replay. Credit also declares that request queue before
publishing so a request can wait while User is offline.

User and Credit must use the same RabbitMQ broker and virtual host. The Compose
allocation can be overridden with `INITIAL_CREDIT_ALLOCATION`; the gateway uses
the shared `INTERNAL_GATEWAY_URL`. `/health` remains the container liveness check.

To demonstrate registration-to-allocation, open User Service's Swagger at
<http://localhost:5005/docs>, register using `POST /authentication/users`, and
sign in using `POST /authentication/sessions`. In Credit's Swagger at
<http://localhost:3002/docs>, call `GET /credits/current`; the sign-in cookie is
available on the same hostname, and the initialized balance is `100` available
and `0` reserved with the default configuration. A temporary `404` means the
event has not been processed yet; retry after allocation completes.

For delayed delivery, stop Credit, register another account, then start Credit
and fetch that account's balance after signing in. Restarting Credit again
requests another reconciliation but keeps the existing wallet and balance.
