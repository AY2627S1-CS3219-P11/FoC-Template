# User Service

Minimal FastAPI service for Campus Errands. Python 3.14 or newer and uv are required.
Authentication routes are scaffolded. There is no health endpoint or database schema.

```text
user-service/
├── src/
│   ├── auth/
│   │   ├── views.py
│   │   ├── service.py
│   │   ├── models.py
│   │   └── exceptions.py
│   ├── common/
│   │   ├── config_manager.py
│   │   └── db.py
│   └── main.py
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── pyproject.toml
└── uv.lock
```

Run from `user-service/`:

```sh
uv sync
cp -n .env.example .env
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 5005
```

API documentation is available at [localhost:5005/docs](http://localhost:5005/docs).

Copy `.env.example` to `.env`, then fill in `DATABASE_URL` and
`ACCESS_TOKEN_SECRET` before starting the service. Keep `.env` local; Git ignores it.

The existing frontend sends `/api/*` requests through Vite to
`http://127.0.0.1:5005`, stripping `/api`. Run `npm run dev` from `ui/` in
another terminal. `/api/openapi.json` reaches this service's `/openapi.json`.
The layout follows `ai-know-backend`: each feature owns its endpoint handlers in
`views.py`, logic and database calls in `service.py`, data types in `models.py`,
and domain errors in `exceptions.py`. `src/main.py` registers the feature routers.
Shared settings and database connections belong in `src/common`.

For VS Code, open `user-service` and run `User Service: FastAPI`. The launch
configuration uses `src` as its working directory and loads the service-root `.env`.

For direct requests across origins, set the frontend's `VITE_API_URL` to
`http://127.0.0.1:5005`. `CORS_ORIGINS` is a JSON array of trusted frontend origins;
it defaults to `http://localhost:5173` and `http://127.0.0.1:5173`.
Update it if the frontend uses a different port or production domain.
Credentialed CORS is enabled to match the frontend's cookie-based requests.

Authentication follows Job Tracker's bcrypt cost-10 password hashing and HS256
JWT signing. Passwords are limited to 72 UTF-8 bytes. Access tokens expire after
15 minutes. Store a cryptographically random `ACCESS_TOKEN_SECRET` of at least
32 bytes in the ignored `.env` or deployment secrets. It is a signing key, not a
password hash or an access token. App name and CORS defaults stay in Python.

| Method | Path | Behavior |
| --- | --- | --- |
| POST | `/authentication/sessions` | Verify password and issue an access-token cookie |
| GET | `/authentication/sessions/current` | Validate the cookie's signature, expiry, and claims |
| DELETE | `/authentication/sessions/current` | Clear the cookie and return 204 |

`src/auth/service.py` contains the SQL lookup placeholder. Until it is
implemented, the lookup returns no user, so sign-in returns 401 and issues no token.
There is no database query or database write in these handlers.

The cookie is HttpOnly with `Path=/`, so it works through Vite and on the direct
API origin. Local defaults are `cookie_secure=False` and `cookie_samesite="lax"`.
For cross-site HTTPS deployment, configure `COOKIE_SECURE=true` and
`COOKIE_SAMESITE=none` in the deployment environment. Browser third-party cookie
policies can still restrict cross-site cookies. Sign-in and sign-out reject
untrusted browser origins; configure the trusted frontend origins explicitly.

There are no refresh tokens or session-table writes. Sign-out clears the browser
cookie; a separately copied token remains valid until expiry without server-side
revocation. Future backend routes must enforce token verification independently
of the frontend route guard.

The app uses [FastAPI's CORS middleware](https://fastapi.tiangolo.com/tutorial/cors/).

Run checks:

```sh
uv lock --check
```

Set `DATABASE_URL` in the ignored `.env` file to the PostgreSQL connection URL.
`common.db.get_db_connection` can be used as a FastAPI dependency through
`Depends(get_db_connection)`. It opens a connection when requested and closes it
afterward. Settings mask the connection URL when represented as text.
No schema, tables, migrations, or startup database queries are created.
