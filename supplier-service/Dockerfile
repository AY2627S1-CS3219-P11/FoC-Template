FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /bin/

WORKDIR /app

# Install dependencies as per uv.lock
COPY supplier-service/pyproject.toml supplier-service/uv.lock ./
COPY packages/foc-auth /packages/foc-auth

RUN uv sync --locked --no-dev --no-install-project

COPY supplier-service .

# Use the virtualenv created by uv
ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 3001

CMD ["fastapi", "run", "src/main.py", "--port", "3001"]
