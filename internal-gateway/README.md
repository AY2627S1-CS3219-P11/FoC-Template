# Internal gateway

Nginx routes HTTP calls through one configured `INTERNAL_GATEWAY_URL`:

| Gateway path | Backend path | Compose backend |
| --- | --- | --- |
| `/user-api/<path>` | `/<path>` | `user-service:5005` |
| `/supplier-api/<path>` | `/<path>` | `supplier-service:3001` |
| `/health` | Gateway liveness check | No backend |

The gateway strips only the service prefix and preserves methods, query
strings, bodies, authorization headers, cookies, and upstream status codes.
Authentication and authorization remain in the services. Supplier verifies
callers through `/user-api/authentication/sessions/current`.

## Local Docker setup

After configuring the backend `.env` files, run from the repository root:

```sh
docker compose up --build
```

Open <http://127.0.0.1:4173>. The request path is:

```text
Browser → UI nginx → internal-gateway → user-service / supplier-service
```

The gateway listens on port 80 inside Docker and has **no published host port**
or `extra_hosts` entries. Containers on the shared Compose network reach it at
`http://internal-gateway`; browsers enter through the UI instead. No gateway
host-port settings or additional Compose files are needed.

## Configuration boundary

- Compose supplies service names and Docker DNS for this local topology.
  Application code does not assume localhost or silently choose a gateway.
- Callers configure `INTERNAL_GATEWAY_URL`. Only the gateway configures
  `USER_SERVICE_UPSTREAM` and `SUPPLIER_SERVICE_UPSTREAM`; these must be origins
  without path prefixes or trailing slashes.
- The nginx images require their runtime URL and resolver settings. Supplier
  also refuses to start without its required gateway/dependency configuration.
- `NGINX_DNS_RESOLVER` is deployment configuration; Compose supplies Docker's
  embedded resolver. The gateway resolves peers dynamically, so it can start
  without them and discover recreated containers without a reload.
- `/health` checks nginx itself using loopback inside the container. It does
  not prove backend readiness or network reachability.
- RabbitMQ and databases are separate dependencies, not gateway routes.

Root overrides are documented in [`.env.example`](../.env.example). Deployment
to separate machines needs its own reachable addresses, networking, and security
rules; that topology is outside this local Compose configuration.

## Troubleshooting UI 502s

Inspect the proxy logs and gateway network attachment:

```sh
docker compose logs --tail=50 ui internal-gateway
docker inspect "$(docker compose ps -q internal-gateway)" \
  --format '{{json .NetworkSettings.Networks}}'
curl -f http://127.0.0.1:4173/user-api/health
```

`internal-gateway could not be resolved` indicates a service-discovery problem.
The gateway must be on the same network as the UI; an empty network map (`{}`)
is not normal. If needed, recreate just the gateway:

```sh
docker compose up -d --no-deps --force-recreate internal-gateway
```

Allow a few seconds for cached Docker DNS records to expire after recreation.
`docker compose ps` showing `80/tcp` without a host mapping is expected.

## Routing tests

With Docker Compose and Python installed, run from the repository root:

```sh
python3 -m unittest discover -s internal-gateway/tests -v
```

Tests use an isolated Compose project with echo backends and a random loopback
UI port, then remove its containers and network. They cover an unpublished
gateway, backend-independent startup, missing runtime settings, routing through
the UI and gateway, prefix stripping, request/cookie forwarding, upstream
statuses, rejected gateway routes, and SPA fallback. No application secrets,
databases, or RabbitMQ are needed.
