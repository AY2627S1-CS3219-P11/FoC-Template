# Keycloak authentication

The UI signs in through Keycloak using authorization code flow with S256 PKCE.
Access and refresh tokens stay in memory. Before authenticated API calls, the UI
refreshes its access token and sends it as an Authorization bearer token through
the routing gateway. Both backends independently validate the signature,
issuer, audience, expiry, UUID subject and application role. They also check the
Keycloak session through token introspection so logout and role changes revoke
existing access immediately. Supplier-service never calls user-service to
verify a Keycloak token. A Keycloak outage returns 503 for protected requests.

User-service owns application account creation and profile/role edits, calling
Keycloak administration to keep both stores in sync. New accounts use the same
UUID in both stores; Keycloak owns their password. Existing application data,
supplier audit IDs, requester/courier selection and RabbitMQ behavior are retained.
The gateway forwards Authorization headers and continues to handle routing.

## Local setup

Start Docker Desktop. Copy the root `.env.example` and both backend examples to
`.env` if needed; preserve existing database and bootstrap account values.
Set `KEYCLOAK_DB_PASSWORD`, `KEYCLOAK_ADMIN_PASSWORD` and
`KEYCLOAK_BACKEND_CLIENT_SECRET` and `KEYCLOAK_API_CLIENT_SECRET` to separate local secrets in the root `.env`.
Never put either client secret in a UI `VITE_*` variable. Configure the
application databases in their existing service environment files.

To start identity infrastructure independently from the repository root:

```sh
docker compose -p foc-template --env-file .env -f keycloak/compose.yaml up -d --wait
python3 keycloak/configure.py --env-file .env
```

The script updates clients, service-account permissions and profile settings
in an existing realm without deleting application users. Run it after changing
this configuration or when upgrading a previously started local realm. Startup
realm import alone skips realms that already exist. Bootstrap admin credentials
apply only on first initialization; changing `.env` does not reset that password.

Use the same Compose project name for standalone and root commands so they share
the Keycloak database volume. Open <http://localhost:8080/admin/> using the root
`KEYCLOAK_ADMIN_USERNAME` and `KEYCLOAK_ADMIN_PASSWORD`. This infrastructure admin
is separate from the FoC application's `admin_manager` account.

For an empty application database, user-service creates the configured initial
admin manager in Keycloak and PostgreSQL at startup. For an existing database,
complete the account import below before switching the application to Keycloak.
Then set root `AUTH_PROVIDER=keycloak` and start the stack:

```sh
docker compose up -d --build
```

Open <http://localhost:4173>. Host-run UI development uses `ui/.env.local`,
including `VITE_AUTH_PROVIDER=keycloak`, and needs a reachable internal gateway.
Host-run backends use `KEYCLOAK_SERVER_URL=http://localhost:8080` and the public
JWKS URL; copy the API client secret into both backend environment files and the
administration client secret into user-service only.
Docker backends use `http://keycloak:8080` internally but validate the public
issuer `http://localhost:8080/realms/foc`. If changing Keycloak's port, update
`KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_ISSUER` and host-run settings to match, then
rebuild the UI. Browser auth configuration is embedded at build time.

## Account flows

- Signup retains the UI's form and validation. User-service creates a Keycloak
  account with the `user` role, then stores its UUID and application profile.
  New passwords are not hashed or stored in the application database.
- Sign in redirects to Keycloak. The legacy password-login endpoint returns 409
  in Keycloak mode; it does not issue legacy sessions or cookies.
- Profile edits update Keycloak and the application profile. Keycloak's account
  console cannot independently edit username/email, avoiding profile drift.
- Admin managers can grant/revoke `admin` access through the existing portal.
  Role edits synchronize both stores and revoke the target user's sessions;
  the user signs in again to obtain current permissions. Admin managers remain
  protected from this endpoint.
- UI logout ends the Keycloak browser session. The backend logout endpoint also
  supports revoking the session identified by a bearer token for API clients.

When an application database operation fails after changing Keycloak, the service
attempts to undo the identity change. This is a compensating operation across two
systems, not a distributed transaction. If Keycloak is unavailable during that
undo, reconcile the affected identity before retrying. Make application account
and role changes through user-service rather than manually editing Keycloak.

## Existing-account import

Existing PostgreSQL user UUIDs must be preserved: they are already referenced by
other services. No accounts are automatically linked by email. Stop account
creation/profile/role writes while taking and importing the account snapshot.
This command only reads the configured application database and writes local
files; it does not import users or modify PostgreSQL:

```sh
cd user-service
uv run --locked python -m auth.export_keycloak_users --output ../keycloak/generated/account-import
```

It creates `foc-users.json` and `temporary-passwords.csv` with restrictive file
permissions. The output folder is git-ignored and files are never overwritten.
In the Keycloak admin console, select `foc`, open the realm's partial import
(action menu), and import `foc-users.json` with users selected and conflicts set
to **Fail**. Check that imported IDs equal the application's UUIDs and all three
application roles are represented correctly, including the admin manager.

Existing bcrypt password hashes are not imported. Each user gets a unique
random temporary password from the CSV and must set a new password on first
login. Deliver those credentials privately; delete the generated files after the
handoff. The initial admin's environment password does not replace a migrated
account's temporary password. Email-based password reset needs SMTP configuration
and remains disabled in the local realm. Finish import before enabling Keycloak
on the UI and both backends together. `AUTH_PROVIDER=legacy` remains available
for the previous application flow, but newly created Keycloak accounts have no
legacy password and cannot use that login.

## Realm and database

| Setting | Value |
| --- | --- |
| Realm | `foc` |
| Browser client | Public `foc-ui`, authorization code and S256 PKCE |
| API audience / introspection client | Confidential `foc-api`, with no service account or administration roles |
| Backend client | Confidential `foc-backend`, service account for user administration, available to user-service only |
| Application roles | `user`, `admin`, `admin_manager` |
| UI origins | `localhost` and `127.0.0.1`, ports 4173 and 5173 |
| Access token lifespan | Five minutes, refreshed by the UI before requests |
| Self-registration | Disabled; application signup provisions both stores |

`keycloak-db` owns a separate `keycloak-postgres-data` volume. Its `KEYCLOAK_DB_*`
credentials are independent of Neon and the application databases. PostgreSQL
and Keycloak's management port have no published host ports. The HTTP port is
bound to loopback. Stopping containers retains identity data; deleting the volume
removes accounts. The root realm file contains environment placeholders for
the client secrets, not committed credentials.

Cloud hosting is configured separately: this local stack uses `start-dev` and
HTTP. Production requires HTTPS, deployment-specific hostname/origins, secrets,
production startup settings and a persistent identity database.

## Validation

```sh
uv run --directory user-service --locked pytest -q
uv run --directory supplier-service --locked pytest -q
uv run --directory supplier-service --locked pytest ../packages/foc-auth/tests -q
cd ui
npm run build
npm run lint
```

Swagger accepts a Keycloak **access token** using Authorize at
<http://127.0.0.1:5005/docs> and <http://127.0.0.1:3001/docs>. User-service requires
the signed subject to exist in its application database; supplier audit fields
use that subject UUID. Supplier listing remains public; writes require `admin`
or `admin_manager`. Invalid/inactive tokens return 401, insufficient roles 403,
and unavailable identity verification 503. Legacy tokens are rejected in
Keycloak mode without falling back to user-service.

References: [JavaScript adapter](https://www.keycloak.org/securing-apps/javascript-adapter),
[containers](https://www.keycloak.org/server/containers),
[realm imports](https://www.keycloak.org/server/importExport).
