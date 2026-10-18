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

The development server forwards the user, supplier, order, and credit API prefixes unchanged to the [internal gateway](../internal-gateway/README.md). Host-run development requires an explicitly configured, reachable `INTERNAL_GATEWAY_URL` in `.env.local` or the environment; the dev server refuses to start without it. The local Docker stack intentionally does not publish a gateway host endpoint, so it does not provide that host-run workflow.

This server-side setting is not exposed to the browser. Static builds do not require a gateway address; the nginx runtime receives it from deployment configuration.

For deployments with an external gateway, set `VITE_USER_API_URL`, `VITE_SUPPLIER_API_URL`, `VITE_ORDER_API_URL`, and `VITE_CREDIT_API_URL` at build time.

## Docker

From the repository root, with the backend `.env` files configured:

```sh
docker compose up --build
```

Open <http://localhost:4173>. The UI image builds with Node.js 22 and serves
static assets through Nginx, including SPA route fallback. Root `compose.yaml`
configures one `INTERNAL_GATEWAY_URL` (default `http://internal-gateway`);
API requests stay on the browser's origin and retain their `/user-api`,
`/supplier-api`, `/order-api`, or `/credit-api` prefix until the internal gateway routes them to a backend.
The gateway is reachable only on the shared Docker network. No additional
Compose files or gateway host-port settings are needed. This is a production-style
build, not a hot-reloading dev server.

## Build

```sh
npm run build
```

## Orders

`/orders` is available to every signed-in user. Requesting and delivering are
concurrent capabilities, not account modes. The page offers open requests,
personal requests, personal deliveries, active-supplier selection, item quantities,
delivery location, pickup notes, whole-credit rewards, and balance information.
Lists and balances refresh every five seconds; open-request countdowns update
every second using the server's `expires_at` timestamp.

Orders start at `init` while reserving credits, then become `open` and available
for acceptance or cancellation. `received` awaits credit transfer; `completed`
confirms settlement. Expired requests disappear from the open list; the backend
handles expiry, refunds, and disputes. Personal lists retain order history.

The order API has no separate delivery-location field, so delivery location and
pickup notes are stored together in `pickup_notes` with explicit labels. Initial
credit allocation, atomic acceptance, lifecycle authorization, supplier validation,
expiry and settlement remain backend responsibilities; the UI does not emulate
these financial guarantees.

## Checks

```sh
npm run lint
npm run build
```

For an end-to-end check, sign in as two users: create a request, verify its
reservation and countdown, accept it as the other user, mark pickup and delivery,
then confirm receipt as requester. Check that only the assigned courier sees
progress actions. Test cancellation before acceptance, a 15-minute expiry,
insufficient credits, and two couriers racing to accept the same request. The
server should reject the losing acceptance and any stale cancellation; the UI
surfaces that error and refreshes all lists.

## Preview build

```sh
npm run preview
```
