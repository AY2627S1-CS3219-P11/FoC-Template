# Supplier service

The service exposes active supplier browsing plus administrator-only create,
update, and soft-delete operations.

## Local Docker setup

Configure `SUPPLIER_DATABASE_URL`, `RABBITMQ_USER`, `RABBITMQ_PASSWORD` and
`RABBITMQ_URL` in the root `.env`, then run `docker compose up --build` from
the repository root. Supply an async SQLAlchemy PostgreSQL URL for your own
database; no remote database hostname is built in. Configure TLS for remote
connections and percent-encode URL credentials. The broker URL credentials must
match the broker's configured user/password. Host-run services use `DATABASE_URL`
and a broker URL with `localhost` instead of Docker DNS; export the settings from
`.env.example` before starting the application. See the
[gateway guide](../internal-gateway/README.md).

`RABBITMQ_URL` and `DATABASE_URL` are required. Supplier does not call
user-service for authentication. Other deployment topologies must supply
reachable dependency addresses themselves.

## Authentication

Authentication uses Keycloak exclusively. Configure
`KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE` and `KEYCLOAK_JWKS_URL`.
Supplier-service needs no Keycloak client secrets.
Protected requests validate signed access tokens through the service-local
`auth/tokens.py` adapter using cached JWKS, without introspection. They never call user-service or the gateway for verification,
and never fall back to another authentication mechanism on errors. See the
[Keycloak guide](../user-service/keycloak/README.md) for setup.

Swagger at <http://127.0.0.1:3001/docs> accepts Keycloak access tokens through
Authorize. Invalid/expired tokens return 401, missing permissions return 403,
and unavailable identity verification returns 503. `admin` and `admin_manager`
retain write permissions; supplier listing remains public. Supplier audit UUIDs
come from the signed subject, preserving existing account references.
Already-issued tokens retain access until expiry (up to five minutes), even
after logout or demotion. Validation uses no clock leeway. Cached signing keys
allow validation during Keycloak outages; failed key retrieval returns 503.

## Tests

```sh
uv run --locked python -m pytest -q
```
