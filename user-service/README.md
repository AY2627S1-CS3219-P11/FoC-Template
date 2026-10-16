# User Service

## Local development

Run from `user-service/`:

```sh
uv sync
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 5005
```

## Docker Compose

Run from the repository root:

```sh
docker compose up --build user-service
```
