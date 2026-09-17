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
