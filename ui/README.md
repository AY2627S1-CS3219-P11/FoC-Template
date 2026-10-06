# Campus Errands UI

React and TypeScript frontend for Campus Errands.

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

The development server forwards both API prefixes unchanged to the [internal gateway](../internal-gateway/README.md). Set `INTERNAL_GATEWAY_URL` in `.env.local` or the environment; the dev server refuses to start without it. Start the gateway alongside the backends first. For host-run development:

```sh
INTERNAL_GATEWAY_URL=http://127.0.0.1:8080 npm run dev
```

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
This is a production-style build, not a hot-reloading dev server.

## Build

```sh
npm run build
```

## Preview build

```sh
npm run preview
```
