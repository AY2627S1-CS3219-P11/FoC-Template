# Supplier service

The service exposes active supplier browsing plus administrator-only create,
update, and soft-delete operations.

## Local Docker setup

After configuring the backend `.env` files, run `docker compose up --build` from
the repository root. Compose supplies `http://internal-gateway` and the broker
address. The gateway is reachable on the shared Docker network, not through a
published host port. See the [gateway guide](../internal-gateway/README.md).

`RABBITMQ_URL` and `DATABASE_URL` are required in both authentication modes.
Legacy mode also requires `INTERNAL_GATEWAY_URL`. The gateway URL must be an
HTTP(S) origin; malformed values and URLs with credentials, paths, queries, or
fragments are rejected. Supplier does not configure or call a user-service
hostname directly. Other deployment topologies must supply reachable dependency
addresses themselves.

## Authentication

Root Compose and `.env.example` use `AUTH_PROVIDER=keycloak`. Configure
`KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE` and `KEYCLOAK_JWKS_URL`.
Supplier-service needs no Keycloak client secrets.
Protected requests validate signed access tokens through the service-local
`auth/tokens.py` adapter using cached JWKS, without introspection. They never call user-service or the gateway for verification,
and never fall back to legacy validation on errors. See the
[Keycloak guide](../keycloak/README.md) for setup and account import.

Swagger at <http://127.0.0.1:3001/docs> accepts Keycloak access tokens through
Authorize. Invalid/expired tokens return 401, missing permissions return 403,
and unavailable identity verification returns 503. `admin` and `admin_manager`
retain write permissions; supplier listing remains public. Supplier audit UUIDs
come from the signed subject, preserving existing account references.
Already-issued tokens retain access until expiry (up to five minutes), even
after logout or demotion. Validation uses no clock leeway. Cached signing keys
allow validation during Keycloak outages; failed key retrieval returns 503.

`AUTH_PROVIDER=legacy` retains the previous cookie/token flow, forwarding tokens
to `GET /user-api/authentication/sessions/current` through the gateway.
Switch the UI and both backends together after account import.

## Tests

```sh
uv run pytest
```
