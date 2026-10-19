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

The separate local control portal at <http://127.0.0.1:4180> starts/stops the
actual User, Supplier, Order, Credit, and RabbitMQ containers. It is not an HTTP
or AMQP isolation toggle. A stopped backend normally produces a gateway `502`;
starting it may take a few seconds before requests succeed. The portal uses a
privileged Docker socket mount and must stay local-only. See the [gateway
control documentation](../internal-gateway/README.md#local-dashboard-start-and-stop-containers)
for setup, recovery order, and security restrictions.

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
confirms settlement. While the Orders page is open, reservation transitions show
requesters a popup and completed settlements show couriers a payout popup.
Historical orders do not trigger popups on initial load. Accepting a request
requires confirmation that acceptance cannot be rescinded. Credit balance outages
do not block submission: reservation is handled asynchronously by the backend.
Expired requests disappear from the open list; the backend
handles expiry, refunds, and disputes. Personal lists retain order history.

The order API has no separate delivery-location field, so delivery location and
pickup notes are stored together in `pickup_notes` with explicit labels. Initial
credit allocation, atomic acceptance, lifecycle authorization, supplier validation,
expiry and settlement remain backend responsibilities; the UI does not emulate
these financial guarantees.

### Submission retries and cancellation

Order-list outages do not block new submissions. Each submission freezes its
payload and idempotency key; network errors, timeouts, HTTP 408/429 and server
errors retry with exponential backoff and jitter (up to six attempts per cycle,
with delays capped at 15 seconds). After that, **Retry same request** resumes
using the original key, rather than creating a duplicate. Definitive errors stop
automatic retries.

**Cancel request** records cancellation intent, recovers the order ID by replaying
the same creation, then requests cancellation. While the order is `init`, it waits
for reservation before attempting cancellation. A lost cancellation response is
reconciled against the current order state. Cancellation is not confirmed until
the server reports `cancelled`; an accepted or otherwise non-cancellable order is
reported as such. A missing order is not treated as successful cancellation.

Pending attempts and cancellation intent are currently held in page memory only.
Keep the Orders page open until the outcome is confirmed; leaving it stops local
retries and does not cancel a server-side order. Reloading loses the pending key.

### Demonstrate a lost creation response

The console hook is built into the UI; no environment flag is required. It is
inactive until armed and only affects order creation, not polling or cancellation.
Open the browser console and run:

```js
orderDemo.dropNextCreateResponse()
```

Submit a request normally. The real POST reaches the server; the hook discards
one successful response before the UI sees it, logs the simulated loss, and
automatically disarms. The UI retries with the same payload and `Idempotency-Key`
(visible in the Network panel). Confirm that the retry returns the same order ID,
there is only one order, and credits were reserved only once. Stopping and
restarting Order Service separately demonstrates availability recovery; losing a
successful response demonstrates why idempotency is necessary.

### Credit Service outages and initialization expiry

Order Service defaults to a 60-second initialization deadline
(`ORDER_INIT_TIMEOUT_SECONDS`), distinct from the 15-minute open-order deadline.
If credit reservation is not confirmed in time, the order becomes `expired` even
though its unresolved credit command continues to be retried. A late successful
reservation queues a compensating release; it does not reopen the expired order.

RabbitMQ publisher confirmation means the broker accepted a command, not that
Credit Service processed it. Durable queues can retain commands while the consumer
is stopped, and Order Service also replays unresolved commands (by default after
60 seconds). For a recovery-to-open demo, restart Credit Service early enough for
the reservation result to arrive before initialization expires, or increase
`ORDER_INIT_TIMEOUT_SECONDS` in the Order Service environment and recreate that
service before creating a fresh order. Changing the deadline does not revive an
already expired order.

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
