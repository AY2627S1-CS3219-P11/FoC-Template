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

In the default `AUTH_PROVIDER=legacy` mode, protected operations forward the caller's bearer token (or `access_token`
cookie) as an Authorization header to `GET /user-api/authentication/sessions/current`
on the gateway. Nginx routes this to user-service's existing session validation
endpoint. Authentication and role checks remain unchanged; `admin` and
`admin_manager` may create, edit, and deactivate suppliers.

## Backend Keycloak validation

Set `AUTH_PROVIDER=keycloak`, `KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE`, and
`KEYCLOAK_JWKS_URL` to validate access tokens through the shared
[`foc-auth`](../packages/foc-auth/README.md) package. See `.env.example` for
host-run settings; Compose supplies the internal Docker signing-key address.
Protected requests in this mode make no verification request to the gateway
or user-service, and do not fall back to legacy validation on errors.

Swagger at <http://127.0.0.1:3001/docs> accepts Keycloak access tokens through
Authorize. Authentication errors return 401, missing permissions return 403,
and unavailable signing keys return 503. `admin` and `admin_manager` retain
write permissions; supplier listing remains public. Supplier audit UUIDs come
from the signed subject, so preserve application UUIDs during account migration.

Keep the default legacy mode for the existing UI until its login, account and
role synchronization flows are migrated. User-service and supplier-service
must use the same mode. Account disabling/logout and role changes require the
additional integration; a locally validated JWT remains usable until expiry.

## Tests

```sh
uv run pytest
```
