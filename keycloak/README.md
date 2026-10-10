# Keycloak local development

This setup provides identity infrastructure, a realm template and opt-in
backend token validation. The existing UI still uses legacy authentication by
default. No application users are migrated or created by this setup.

## Start independently

Start Docker Desktop. From the repository root, create `.env` from `.env.example`
if it does not exist, then fill the `KEYCLOAK_*` variables. For an existing `.env`,
add the new variables without replacing other settings. The example passwords
are local development placeholders.

```sh
docker compose -p foc-template --env-file .env -f keycloak/compose.yaml config --quiet
docker compose -p foc-template --env-file .env -f keycloak/compose.yaml up -d --wait
```

This starts only Keycloak and its PostgreSQL database; it needs no Neon, RabbitMQ,
or application service credentials. Root `docker compose up` also includes them.
The commands set `-p foc-template`, matching the default root project name, so
they share containers and the database volume. If you use a custom root project
name, use that same name for the standalone commands.

Open the admin console at <http://localhost:8080/admin/>. Sign in using
`KEYCLOAK_ADMIN_USERNAME` and `KEYCLOAK_ADMIN_PASSWORD`, then select the `foc` realm.
If you change `KEYCLOAK_HTTP_PORT`, use that port instead of 8080 below.

```sh
curl --fail http://localhost:8080/realms/foc/.well-known/openid-configuration
curl --fail http://localhost:8080/realms/foc/protocol/openid-connect/certs
docker compose -p foc-template --env-file .env -f keycloak/compose.yaml ps
```

Both containers should be healthy. Readiness checks include Keycloak's database
connection; the management port and PostgreSQL have no published host ports.
Keycloak's HTTP port is bound to loopback.

## Realm configuration

`realms/foc-realm.json` imports on first startup:

| Setting | Value |
| --- | --- |
| Realm | `foc` |
| Browser client | `foc-ui`, public client, authorization code with S256 PKCE |
| API audience | `foc-api`, included in UI access tokens |
| Application roles | `user`, `admin`, `admin_manager` |
| UI origins | `localhost` and `127.0.0.1`, ports 4173 and 5173 |
| Access token lifespan | 5 minutes |
| Self-registration / password reset | Disabled until account provisioning / email are integrated |

No application accounts or client secrets are embedded in the realm file.
For manual development testing, create a user in the `foc` realm, set a password,
and explicitly assign the appropriate application role. The bootstrap admin is
an infrastructure administrator in the `master` realm, not a FoC application user.

Application integration should use issuer `http://localhost:8080/realms/foc` and
validate audience `foc-api`. Docker backends can retrieve signing keys at
`http://keycloak:8080/realms/foc/protocol/openid-connect/certs`, while still
validating the public issuer above. Container `localhost` refers to the container,
so do not use it as the backend's network address for Keycloak.

Realm roles will appear under `realm_access.roles`; backends must select the
application roles rather than treating every built-in Keycloak role as a FoC role.
Account UUID mapping, signup events, profile synchronization, role changes and
logout invalidation still need to be integrated.

## Persistence and realm changes

`keycloak-db` owns a separate `keycloak-postgres-data` named volume. Its credentials
are the `KEYCLOAK_DB_*` variables, independent of the application databases.
Stopping containers preserves identity data:

```sh
docker compose -p foc-template --env-file .env -f keycloak/compose.yaml stop
```

Startup import skips realms that already exist. Editing the JSON and restarting
will not update an existing `foc` realm. Apply changes through the admin console
or delete just the disposable `foc` realm in the console and restart Keycloak to
reimport it; deletion removes its users and configuration. Do not use root
`docker compose down --volumes` as a realm reset, because it affects other volumes.
Bootstrap admin credentials also apply only to first initialization; changing
the environment does not change an existing admin's password.

## Deployment scope

This Compose configuration uses `start-dev` and local HTTP. Cloud hosting will
be configured separately with a production startup configuration, HTTPS,
deployment-specific hostname, credentials and persistent database. The local
settings do not change application authentication or gateway routing.

References: [container setup](https://www.keycloak.org/server/containers),
[realm imports](https://www.keycloak.org/server/importExport),
[health checks](https://www.keycloak.org/observability/health).

## Infrastructure validation

Validated in an isolated Compose project:

- Root and standalone Compose configuration match, including the realm mount.
- PostgreSQL and Keycloak reach healthy status, with successful realm import.
- The realm survives stopping/restarting both containers; import skips it on restart.
- Discovery, signing keys, application roles and UI client settings are present.
- An authorization-code login with S256 PKCE produces an access token containing
  the expected issuer, subject, email, `user` role and `foc-api` audience.

This verifies identity infrastructure, not integration with the application UI
or protected backend endpoints. Those remain on the existing authentication.

## Backend validation

Both services install [`packages/foc-auth`](../packages/foc-auth/README.md) and
can validate Keycloak access tokens locally. The gateway continues to route
requests and forward their Authorization headers.

For isolated backend validation, set `AUTH_PROVIDER=keycloak` in the root `.env`
and recreate both backend containers. The root `.env.example` contains issuer,
audience and signing-key URL settings. Start Keycloak before sending protected
requests. In this mode supplier-service makes no verification call to user-service,
and user-service does not consult its legacy authentication-session table.

Use a Keycloak access token in each Swagger Authorize dialog. User-service also
requires the token's subject UUID to exist in its application database. Supplier
audit fields use that same UUID. Plan existing-account import with preserved IDs;
do not link accounts by matching email addresses.

Keep `AUTH_PROVIDER=legacy` for the current UI. UI login/refresh/logout,
Keycloak account creation, profile synchronization, role-edit synchronization,
and migration of existing users still need to be integrated. The existing database role
editing endpoint does not update Keycloak yet. Local JWT validation also cannot
immediately invalidate an already-issued token after logout or a role change.
Do not treat backend validation mode as the completed application cutover.

```sh
uv run --project supplier-service --locked pytest -q
uv run --project user-service --locked pytest -q
uv run --project supplier-service --locked pytest packages/foc-auth/tests -q
docker compose build user-service supplier-service
```
