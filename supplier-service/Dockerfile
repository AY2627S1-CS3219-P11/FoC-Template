FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /bin/

WORKDIR /app

# Install dependencies as per uv.lock
COPY pyproject.toml uv.lock ./

RUN uv sync --locked --no-dev --no-install-project

COPY . .

# Use the virtualenv created by uv
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 3001

CMD ["fastapi", "run", "src/main.py", "--port", "3001"]