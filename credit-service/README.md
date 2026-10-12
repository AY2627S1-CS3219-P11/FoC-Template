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

## Current balance

`GET /credits/current` returns only `available_credits` and `reserved_credits`
from the authenticated user's stored balance. Through the UI/gateway, use
`GET /credit-api/credits/current`. Swagger accepts an access token through
**Authorize**; requests without an Authorization header use the `access_token`
cookie. An explicitly supplied invalid token is rejected.
Missing or invalid tokens return `401`, unavailable verification returns `503`,
and an account still awaiting initialization returns `404`.

## Initial allocation and existing accounts

New registrations save a `UserCreated` event in User Service's outbox in the
same transaction as the account. The publisher retries until RabbitMQ confirms
persistent delivery. Credit commits the configured allocation before
acknowledging; a repeated user ID leaves existing balances and timestamps intact.

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
