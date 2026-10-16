# Credit Service

## Local development

Run from `credit-service/`:

```sh
uv sync
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 3002
```

## Docker Compose

Run from the repository root:

```sh
docker compose up --build user-service credit-service
```
