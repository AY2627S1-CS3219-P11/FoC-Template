# User service

Owns application account policy, bootstrap and the admin-manager API. Keycloak
owns credentials, username, email, sessions and coarse application roles.
There is no application identity database: the previous SQL table contained no
genuine application profile data. Future application-only profile data should
be keyed by a validated subject, not duplicate identity fields or roles.

## Development

Python 3.14+ and `uv` are required. Configure `.env` from `.env.example`, then:

```sh
uv sync
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 5005
uv run --locked python -m pytest -q
```

Open <http://127.0.0.1:5005/docs>. Tests use mock Keycloak responses, not a database.
See the [Keycloak guide](keycloak/README.md) for local infrastructure setup.

## API ownership

- Browser signup, login and identity edits belong on Keycloak pages. The API
  does not accept passwords or proxy profile writes.
- `GET /authentication/sessions/current` verifies the bearer token locally.
- `GET /authentication/users/current` reads identity details from Keycloak.
- `GET /authentication/users` lists a bounded page of accounts for managers
  (`role=user|admin`, `offset`, `limit` up to 100). Effective-role and `query`
  filtering apply within that page, including inherited user roles; protected
  managers are omitted. Filtered pages can be empty while more accounts remain.
- `PATCH /authentication/users/{id}/role` permits managers to set only `user` or
  `admin`. Targets with an effective admin-manager role are protected. Other
  realm roles are preserved. Infrastructure/composite roles remain an operator
  responsibility, not an application capability.

Each backend validates signature, issuer, audience, expiry and permissions with
its own cached-JWKS adapter. Verification needs no SQL lookup, user-service call,
introspection or client secret. Already-issued tokens remain valid until expiry
(up to five minutes after logout/demotion), with no clock leeway. Role changes
are idempotent requests to Keycloak, not cross-database transactions or forced
logouts; failed multi-step role changes may require retry/operator inspection.

Only user-service receives the administration client secret. Keycloak failures
in identity reads/writes return 503; missing accounts return 404. A cached-key
JWT can remain valid during a Keycloak outage.

## Bootstrap

Startup skips bootstrap if Keycloak already has an admin-manager role member.
Otherwise it creates the configured initial manager disabled, grants its role,
then enables it. A conflicting username is never adopted or promoted. If setup
fails, inspect the disabled account in Keycloak and reconcile it before retrying;
there is no destructive compensation or automatic account migration. Bootstrap
credentials are used only for the initial account, not password resets.
