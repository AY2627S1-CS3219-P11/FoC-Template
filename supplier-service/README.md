# Supplier service

The service exposes active supplier browsing plus administrator-only create, update, and soft-delete operations.

Set `DATABASE_URL` for PostgreSQL and `INTERNAL_GATEWAY_URL` for the shared HTTP gateway origin. For example, with services running directly on the host and the [internal gateway](../internal-gateway/README.md) running on port 8080:

```sh
export DATABASE_URL=postgresql+psycopg://supplier:supplier@localhost:5432/supplier
export INTERNAL_GATEWAY_URL=http://127.0.0.1:8080
export RABBITMQ_URL=amqp://admin:admin123@127.0.0.1:5672
uv run fastapi dev src/main.py --port 3001
```

Protected operations forward the caller's bearer token (or `access_token` cookie) as an Authorization header to `GET /user-api/authentication/sessions/current` on the gateway. Nginx routes this to user-service's existing session validation endpoint. Authentication and role checks remain unchanged; `admin` and `admin_manager` may create, edit, and deactivate suppliers.

In the root Docker Compose stack, Compose supplies `http://internal-gateway` and the broker address. Application code has no address fallbacks: missing `INTERNAL_GATEWAY_URL`, `RABBITMQ_URL`, or `DATABASE_URL` prevents startup. The gateway URL must be an HTTP(S) origin; malformed values and URLs with credentials, paths, queries, or fragments are rejected. Supplier does not configure or call a user-service hostname directly.

Run tests with:

```sh
uv run pytest
```
