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

For deployments with an external gateway, set `VITE_API_URL` and `VITE_SUPPLIER_API_URL` at build time.

## Build

```sh
npm run build
```

## Preview build

```sh
npm run preview
```
