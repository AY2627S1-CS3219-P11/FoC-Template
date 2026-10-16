# Keycloak authentication

User-service owns the account capability and its Keycloak configuration. Keycloak
runs as a separate process with its own PostgreSQL database. It owns credentials,
username, unique email, sessions and application roles. There is no mirrored SQL
identity or role store and no legacy account migration path.

## Local setup

Copy root `.env.example` to `.env` and configure `KEYCLOAK_DB_PASSWORD`,
`KEYCLOAK_ADMIN_PASSWORD` and `KEYCLOAK_BACKEND_CLIENT_SECRET` with separate local
secrets. Configure the initial application manager in `user-service/.env`.
Never expose administration secrets through UI `VITE_*` settings.

From the repository root:

```sh
docker compose -p foc-template --env-file .env -f user-service/keycloak/compose.yaml up -d --wait
python3 user-service/keycloak/configure.py --env-file .env
docker compose -p foc-template up -d --build
```

Realm import only applies on first initialization. Run `configure.py` after
configuration changes to update an existing realm. It preserves users, enables
registration/account editing, grants the default `user` role and reapplies the
five-minute token lifespan, clearing client overrides. Bootstrap admin credentials
only apply on first initialization; changing `.env` does not reset the password.
Use the same Compose project name so standalone and root commands share volumes.

Open the app at <http://localhost:4173>. The infrastructure admin console is at
<http://localhost:8080/admin/>; its administrator is separate from the application's
`admin_manager`. User-service creates the configured initial manager only if none
exists. Conflicting usernames are never adopted; failed provisioning leaves a
disabled account for operator reconciliation.

## Browser flows

- Login uses authorization code flow with S256 PKCE through public `foc-ui`.
- Registration uses Keycloak's own page; new users inherit only application `user`
  access through `default-roles-foc`, never administrator privileges.
- Account details and passwords are edited in Keycloak's account console.
- The application manager portal grants/revokes supplier `admin` access through
  user-service. Manager identities and unrelated roles are protected.
- Logout ends the browser session. Tokens stay in memory, not browser storage.

The UI is configured at build time using `VITE_KEYCLOAK_URL`,
`VITE_KEYCLOAK_REALM` and `VITE_KEYCLOAK_CLIENT_ID`. Host-run backends use the public
JWKS URL; Docker backends fetch keys from `http://keycloak:8080` while checking the
public issuer `http://localhost:8080/realms/foc`.

## Verification and revocation

Each backend independently verifies RS256 signatures, issuer, `foc-api` audience,
expiry, UUID subject and application roles using cached JWKS. No introspection,
per-request user-service calls or API client secrets are needed. Only user-service
receives the confidential `foc-backend` administration credentials.

Already-issued tokens remain valid until expiry after logout or demotion, for up
to five minutes. Validators apply no clock leeway: synchronize deployment clocks
and keep the realm lifespan at 300 seconds without client overrides. Cached keys
permit validation during Keycloak outages; failed key retrieval returns 503.
Invalid/expired tokens return 401 and insufficient permissions return 403.

## Deployment

`keycloak-db` has a separate persistent volume. Its database credentials are
independent of application databases. Neither PostgreSQL nor the Keycloak
management port is published; HTTP is bound to loopback. Deleting the volume
removes identities. This local stack uses `start-dev` and HTTP; production needs
HTTPS, explicit origins/hostname, managed secrets and production startup settings.
Password recovery remains disabled until SMTP is configured.

## Checks

```sh
uv run --directory user-service --locked python -m pytest -q
uv run --directory supplier-service --locked python -m pytest -q
cd ui
npm run build
npm run lint
```

Live registration, account editing and session expiry also require testing against
a running Keycloak instance; unit tests alone do not establish those integrations.
