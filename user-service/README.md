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

## Backend Keycloak validation

`AUTH_PROVIDER=legacy` preserves the current UI login and session behavior.
`AUTH_PROVIDER=keycloak` validates protected requests using the shared
[`foc-auth`](../packages/foc-auth/README.md) package and Keycloak realm roles.
Configure `KEYCLOAK_ISSUER`, `KEYCLOAK_AUDIENCE`, and `KEYCLOAK_JWKS_URL` as shown
in `.env.example`. Host-run services use the public signing-key endpoint;
Compose uses `http://keycloak:8080/...` for key retrieval but validates the
public issuer. Include `Authorization: Bearer <Keycloak access token>`, or use
Swagger's Authorize button. Existing access-token cookies are also accepted,
but legacy-issued tokens are rejected in Keycloak mode.

Keycloak `sub` must equal an existing application's user UUID. Unknown subjects
return 401; accounts are never linked by email or provisioned during validation.
Preserve UUIDs when importing existing accounts, and use the Keycloak subject
as the application UUID when implementing future registration.

Keycloak mode supports backend validation before UI cutover. Credentials/sign-up,
Keycloak account provisioning, profile/role synchronization and logout/revocation
are not integrated yet. The existing role-edit endpoint updates the application
database; it does not change Keycloak roles. JWT permissions reflect the roles
at issuance and remain usable until expiry. Keep legacy mode for the current UI
until those flows are implemented together. Both backends must use the same mode.

Tests use an in-memory database and do not connect to Neon:

```sh
uv run --locked pytest -q
```

HTTP calls from other services reach this service through the [internal
gateway](../internal-gateway/README.md), using the `/user-api/` prefix. For
future outbound HTTP calls, use the shared `INTERNAL_GATEWAY_URL`, not a peer
service URL. Compose supplies that setting with a Docker-network default. There
are no outbound HTTP calls today, so user-service does not require an unused
gateway setting to start or assume a localhost destination.
