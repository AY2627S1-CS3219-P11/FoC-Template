# Supplier service

The service exposes active supplier browsing plus administrator-only create, update, and soft-delete operations.

Set `DATABASE_URL` for PostgreSQL and `USER_SERVICE_URL` for the user-service origin. For example, when both services run directly on the host:

```sh
export DATABASE_URL=postgresql+psycopg://supplier:supplier@localhost:5432/supplier
export USER_SERVICE_URL=http://127.0.0.1:5005
uv run fastapi dev src/main.py --port 3001
```

Protected operations forward the caller's `access_token` cookie to `GET /authentication/sessions/current`. The `admin` and `admin_manager` roles may create, edit, and deactivate suppliers.

Run tests with:

```sh
uv run pytest
```
