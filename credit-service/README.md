# Credit Service

## Requirements

- Python 3.14 or newer
- `uv`
- A running RabbitMQ broker

## Install

Run from `credit-service/`:

```sh
uv sync
```

Set `DATABASE_URL` and `RABBITMQ_URL` in `.env` using `.env.example` as a reference.

## Development

For a local Docker broker, use `localhost` as the hostname in `RABBITMQ_URL`.

```sh
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 3002
```

Open <http://127.0.0.1:3002/docs>.

## Docker Compose

Use `rabbitmq` as the hostname in `RABBITMQ_URL`. Run from the repository root:

```sh
docker compose up --build credit-service
```

Open <http://localhost:3002/docs>.
