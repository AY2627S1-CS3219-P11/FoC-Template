# Internal gateway

Nginx is the shared HTTP entry point for service-to-service calls. Callers use
one `INTERNAL_GATEWAY_URL` and a service-specific path, not peer hostnames:

| Gateway path | Backend path | Compose default backend |
| --- | --- | --- |
| `/user-api/<path>` | `/<path>` | `user-service:5005` |
| `/supplier-api/<path>` | `/<path>` | `supplier-service:3001` |
| `/health` | Gateway liveness check | No backend |

Supplier verifies the caller with
`GET ${INTERNAL_GATEWAY_URL}/user-api/authentication/sessions/current`.
The gateway only routes requests; authentication and authorization remain in
the services. Methods, query strings, bodies, authorization headers, cookies,
and upstream status codes pass through unchanged.

## Configuration boundary

- **Application code has no destination fallbacks.** Supplier validates its
  gateway origin before connecting to dependencies. Missing required settings
  prevent startup. User-service has no outbound HTTP calls and therefore does
  not require an unused gateway setting.
- **Compose owns topology defaults.** It supplies `http://internal-gateway`,
  Docker service names, and Docker's DNS resolver. Override these through
  deployment environment variables; no application changes are needed.
- **Only the gateway configures HTTP peers.** `USER_SERVICE_UPSTREAM` and
  `SUPPLIER_SERVICE_UPSTREAM` must be origins without path prefixes or trailing
  slashes. Callers configure the gateway origin, not these upstreams.
- `NGINX_DNS_RESOLVER` is deployment configuration too. Compose uses Docker's
  embedded resolver; a non-Docker nginx deployment must use its own resolver.
- Database and RabbitMQ connections are separate, non-HTTP dependencies. They
  still need their own configuration and do not pass through this gateway.

## Docker Compose

Run `docker compose up --build` from the repository root after configuring the
backend `.env` files. Optional root `.env` overrides are listed in
[`.env.example`](../.env.example). Both UI API prefixes go through the same
origin. The gateway starts without backends and resolves them dynamically,
avoiding circular startup dependencies and stale container IPs.

By default, the host mapping is `127.0.0.1:8080`. Override
`INTERNAL_GATEWAY_BIND_ADDRESS` and `INTERNAL_GATEWAY_PORT` for another deployment
or an occupied port. `/health` checks nginx itself, not backend readiness.

## Host-run development

To route to services running directly on the host, start only the gateway:

```sh
USER_SERVICE_UPSTREAM=http://host.docker.internal:5005 \
SUPPLIER_SERVICE_UPSTREAM=http://host.docker.internal:3001 \
docker compose -f internal-gateway/compose.yaml up --build
```

Host-run callers must explicitly set `INTERNAL_GATEWAY_URL=http://127.0.0.1:8080`
(or the configured host port). This is configuration, not a service fallback.
Docker's host alias is needed only at the gateway, not in every caller.

`0.0.0.0` is a **listen/bind address**, never a peer destination. Loopback in
health checks deliberately checks the local process; it is not service discovery.

## Separate EC2 instances

Deploy each image with its runtime environment instead of treating the root
Compose stack as a multi-host orchestrator. Use reachable private DNS names:

```dotenv
INTERNAL_GATEWAY_URL=http://gateway.foc.internal
USER_SERVICE_UPSTREAM=http://users.foc.internal:5005
SUPPLIER_SERVICE_UPSTREAM=http://suppliers.foc.internal:3001
INTERNAL_GATEWAY_BIND_ADDRESS=0.0.0.0
INTERNAL_GATEWAY_PORT=80
```

The two upstream settings belong **only to the gateway instance**. Each caller
gets `INTERNAL_GATEWAY_URL`; it does not know the backend hostnames. Moving a
backend means changing one gateway upstream (or its DNS record). A stable
gateway DNS name avoids updating callers when the gateway's IP changes.

Configure DNS, network reachability, and security groups separately: allow
callers to reach the gateway and the gateway to reach backend ports on the
private network. Do not expose those ports publicly. Each service still needs
its own database/broker settings where applicable. Add future HTTP services by
adding a gateway route; existing callers retain the same shared origin.

## Routing tests

With Docker Compose 2.24.4+ and Python installed, run from the repository root:

```sh
python3 -m unittest discover -s internal-gateway/tests -v
```

Tests create an isolated Compose project with echo backends and random loopback
ports, then remove its containers and network. They cover backend-independent
startup, missing runtime settings, routing through the gateway and UI, prefix
stripping, request/cookie forwarding, upstream statuses, and SPA fallback.
No application secrets, databases, or RabbitMQ are needed.
