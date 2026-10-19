# Credit Service

## Local development

Run from `credit-service/`:

```sh
uv sync
uv run uvicorn main:app --app-dir src --reload --host 127.0.0.1 --port 3002
```

## Credit operation replies

Replies on `credit.operation.result` contain only `request_id`, `order_id`,
`operation`, `outcome`, and `reason`. Successful replies have a null reason;
rejections carry a rejection reason. The AMQP message type is
`CreditOperationResult`.

The outbox stores the original command alongside the result. Identical retries
replay the decision; request-ID reuse with changed command fields is rejected.

## Docker Compose

Run from the repository root:

```sh
docker compose up --build user-service credit-service
```
