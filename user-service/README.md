# User Service

FastAPI service for user authentication and profiles.

## Requirements

- Python 3.14 or newer
- `uv`

## Install

Run from `user-service/`:

```sh
uv sync
```

## Development

```sh
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 5005
```

Open <http://127.0.0.1:5005/docs>.

HTTP calls from other services reach this service through the [internal
gateway](../internal-gateway/README.md), using the `/user-api/` prefix. For
future outbound HTTP calls, use the shared `INTERNAL_GATEWAY_URL`, not a peer
service URL. Compose supplies that setting with a Docker-network default. There
are no outbound HTTP calls today, so user-service does not require an unused
gateway setting to start or assume a localhost destination.
