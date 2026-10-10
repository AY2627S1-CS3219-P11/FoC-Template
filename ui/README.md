# Campus Errands UI

React and TypeScript frontend for Campus Errands. Use the [Docker setup](#docker)
for the local application stack.

## Requirements

- Node.js
- npm

## Install

Run from `ui/`:

```sh
npm ci
cp .env.example .env.local
```

## Development

```sh
npm run dev
```

Open <http://localhost:5173>.

The development server forwards both API prefixes unchanged to the [internal gateway](../internal-gateway/README.md). Host-run development requires an explicitly configured, reachable `INTERNAL_GATEWAY_URL` in `.env.local` or the environment; the dev server refuses to start without it. The local Docker stack intentionally does not publish a gateway host endpoint, so it does not provide that host-run workflow.

This server-side setting is not exposed to the browser. Static builds do not require a gateway address; the nginx runtime receives it from deployment configuration.

For deployments with an external gateway, set `VITE_USER_API_URL` and `VITE_SUPPLIER_API_URL` at build time.

## Docker

From the repository root, with the backend `.env` files configured:

```sh
docker compose up --build
```

Open <http://localhost:4173>. The UI image builds with Node.js 22 and serves
static assets through Nginx, including SPA route fallback. Root `compose.yaml`
configures one `INTERNAL_GATEWAY_URL` (default `http://internal-gateway`);
API requests stay on the browser's origin and retain their `/user-api` or
`/supplier-api` prefix until the internal gateway routes them to a backend.
The gateway is reachable only on the shared Docker network. No additional
Compose files or gateway host-port settings are needed. This is a production-style
build, not a hot-reloading dev server.

## Build

```sh
npm run build
```

## Preview build

```sh
npm run preview
```

## Authentication

The Docker build uses Keycloak by default. For host development, copy the
`VITE_AUTH_PROVIDER`, `VITE_KEYCLOAK_URL`, `VITE_KEYCLOAK_REALM` and
`VITE_KEYCLOAK_CLIENT_ID` settings from `.env.example` into `.env.local`.
Keycloak browser settings are public build-time configuration; never expose a
backend client secret through a `VITE_*` setting.

Login uses Keycloak's authorization-code flow with S256 PKCE. Tokens stay in
memory and are refreshed before authenticated requests. Signup, profiles,
account-role selection, the admin-manager portal and supplier management retain
their application screens. Logout ends the Keycloak session. Backend services
check permissions independently for every protected request.

See the [Keycloak guide](../keycloak/README.md) for identity setup and the required
import of existing accounts. `VITE_AUTH_PROVIDER=legacy` retains the previous UI
login flow when both backends also use legacy mode.
