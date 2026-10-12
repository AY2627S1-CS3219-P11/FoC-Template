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
`KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE`, `KEYCLOAK_JWKS_URL`,
`KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM` and the API client credentials. Supplier-service does not receive the
account-administration client secret.
Protected requests validate signed access tokens through the shared
[`foc-auth`](../packages/foc-auth/README.md) package and check active sessions
with Keycloak. They never call user-service or the gateway for verification,
and never fall back to legacy validation on errors. See the
[Keycloak guide](../keycloak/README.md) for setup and account import.

Swagger at <http://127.0.0.1:3001/docs> accepts Keycloak access tokens through
Authorize. Invalid/inactive tokens return 401, missing permissions return 403,
and unavailable identity verification returns 503. `admin` and `admin_manager`
retain write permissions; supplier listing remains public. Supplier audit UUIDs
come from the signed subject, preserving existing account references.
Logout and role changes revoke sessions, preventing old tokens retaining access.

`AUTH_PROVIDER=legacy` retains the previous cookie/token flow, forwarding tokens
to `GET /user-api/authentication/sessions/current` through the gateway.
Switch the UI and both backends together after account import.

## Tests

```sh
uv run pytest
```
