# User Service

Minimal FastAPI service for Campus Errands. Python 3.11 or newer is required.
There are no business endpoints or health endpoint yet.

```text
user-service/
├── app/
│   ├── core/
│   │   ├── config.py
│   │   └── database.py
│   ├── routers/
│   └── main.py
├── tests/test_app.py
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
├── requirements.txt
└── requirements-dev.txt
```

Run from `user-service/`:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp -n .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 5005
```

API documentation is available at [localhost:5005/docs](http://localhost:5005/docs).

The existing frontend sends `/api/*` requests through Vite to
`http://127.0.0.1:5005`, stripping `/api`. Run `npm run dev` from `ui/` in
another terminal. `/api/openapi.json` reaches this service's `/openapi.json`.
Add route modules under `app/routers` and register them using `app.include_router`.

For direct requests across origins, set the frontend's `VITE_API_URL` to
`http://127.0.0.1:5005`. `CORS_ORIGINS` is a JSON array of trusted frontend origins;
it defaults to `http://localhost:5173` and `http://127.0.0.1:5173`.
Update it if the frontend uses a different port or production domain.
Credentialed CORS is enabled to match the frontend's cookie-based requests.

Authentication endpoints are not implemented. Future sign-in/sign-out handlers
must set and clear the HttpOnly access-token cookie. Cross-site production
cookies need `SameSite=None; Secure` and HTTPS, together with server-side CSRF
protection. No refresh-token flow is included.

The layout follows [FastAPI's multi-file structure](https://fastapi.tiangolo.com/tutorial/bigger-applications/)
and [CORS configuration](https://fastapi.tiangolo.com/tutorial/cors/).

Run checks:

```sh
python -m pytest -q
python -m pip check
```

Set `DATABASE_URL` in the ignored `.env` file to the PostgreSQL connection URL.
`app.core.database.get_db_connection` can be used as a FastAPI dependency through
`Depends(get_db_connection)`. It opens a connection when requested and closes it
afterward. Settings mask the connection URL when represented as text.
No schema, tables, migrations, or startup database queries are created.
