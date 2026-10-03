# Campus Errands UI

React and TypeScript frontend for Campus Errands.

## Requirements

- Node.js
- npm

## Install

Run from `ui/`:

```sh
npm ci
```

## Development

```sh
npm run dev
```

Open <http://localhost:5173>.

The development server proxies user-service requests to `http://127.0.0.1:5005` and supplier-service requests to `http://127.0.0.1:3001`. Override these targets when needed:

```sh
VITE_API_PROXY_TARGET=http://127.0.0.1:5005 \
VITE_SUPPLIER_API_PROXY_TARGET=http://127.0.0.1:3001 \
npm run dev
```

For deployments with an external gateway, set `VITE_USER_API_URL` and `VITE_SUPPLIER_API_URL` at build time.

## Docker

From the repository root, with the backend `.env` files configured:

```sh
docker compose up --build
```

Open <http://localhost:8080>. The UI image builds with Node.js 22 and serves
static assets through Nginx, including SPA route fallback. Root `compose.yaml`
configures the Nginx upstreams (`USER_API_UPSTREAM` and
`SUPPLIER_API_UPSTREAM`); API requests stay on the browser's origin and are
proxied to the backend containers with the `/user-api` or `/supplier-api`
prefix removed. This is a production-style build, not a hot-reloading dev server.

## Build

```sh
npm run build
```

## Preview build

```sh
npm run preview
```
