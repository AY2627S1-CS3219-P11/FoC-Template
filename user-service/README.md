# User Service

FastAPI service for user authentication and profiles.

## Requirements

- Python 3.14 or newer
- `uv`

## Install

Run from `user-service/`:

```sh
uv sync
```

## Development

```sh
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 5005
```

Open <http://127.0.0.1:5005/docs>.

## Authentication

`AUTH_PROVIDER=keycloak` uses the shared
[`foc-auth`](../packages/foc-auth/README.md) package to validate access tokens
and check active Keycloak sessions. Configure issuer, audience, JWKS URL,
Keycloak server URL, realm and separate API and administration client credentials as shown
in `.env.example`. Root Compose supplies Docker addresses and the root secret;
host-run services need `localhost` addresses and the same client secrets in their `.env`.
See the [Keycloak guide](../keycloak/README.md) for setup and existing-account import.

Signup provisions a Keycloak account and stores its UUID in PostgreSQL. Profile
and role edits synchronize both stores. Role edits revoke existing sessions;
logout revokes the presented session. Keycloak owns credentials and browser
login, so the legacy password-login endpoint returns 409 in this mode.
`AUTH_PROVIDER=legacy` retains the previous cookie/session flow. Switch the UI
and both backends together after importing existing users with preserved UUIDs.

Use `Authorization: Bearer <Keycloak access token>` or Swagger's Authorize button.
The signed subject must match an application user UUID. Unknown subjects return
401; validation never links accounts by email or creates accounts. Tokens are
also accepted from the existing access-token cookie for API compatibility, but
legacy-issued tokens are rejected in Keycloak mode.

Tests use an in-memory database and do not connect to Neon:

```sh
uv run --locked pytest -q
```

HTTP calls from other services reach this service through the [internal
gateway](../internal-gateway/README.md), using the `/user-api/` prefix. For
future outbound HTTP calls, use the shared `INTERNAL_GATEWAY_URL`, not a peer
service URL. Compose supplies that setting with a Docker-network default. Keycloak administration uses its own explicitly configured identity-server URL;
user-service does not require an unused gateway setting to start.
