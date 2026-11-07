# CS3219 — Software Design and Architecture (AY2627 Sem 1)

## Friend on Campus (FoC)

**Friend on Campus (FoC)** is a peer-to-peer campus errand platform where
students can request items to be collected from stores or facilities on
campus, and other students can fulfil (and deliver) those requests. The
platform runs on a closed credit economy — credits cannot be bought,
withdrawn, or exchanged for money, and only circulate within the platform.

---

## Team Members

| Name | Role |
| ----- | ----- |
| Your Name | Your ownership |
| Your Name | Your ownership |
| Your Name | Your ownership |
| Wei Hung | **User Service & Authentication:** Set up a reusable React/Vite frontend template with shared API utilities, components, and layouts, alongside the User Service. Implemented sign-up/sign-in, profile management, JWT-based revocable sessions, protected routes, role-based access control, and the Admin Manager Portal with user search and grant/revoke administrator privileges.<br><br>**Credit Service:** Designed PostgreSQL wallet, reservation, and audit-log schemas; implemented automatic 100-credit allocation via `UserCreated` events, wallet reconciliation, atomic reserve/release/transfer operations with row locking and idempotency, transaction audit logging, and authenticated credit balance/history endpoints.<br><br>**Asynchronous Messaging:** Implemented RabbitMQ user-registration events and credit commands, transactional outbox, publisher confirmations, message acknowledgements/retries, duplicate-request handling, and persistent operation outcomes. Introduced six distinct credit success/rejection events and updated Order Service consumers for compatibility.<br><br>**Frontend & Deployment:** Developed responsive credit audit-log UI with automatic refresh, offset pagination, and error handling; integrated service APIs, configured frontend Docker/Nginx serving and Docker Compose (done as a group), connected services to PostgreSQL/Neon.<br><br>**Prototyping & Documentation:** Developed an initial draft UI prototype, proposed Figma Make for collaborative prototyping, and contributed to the D3 Order Lifecycle Diagram and demo preparation. |
| Your Name | Your ownership |

---

## Repository Structure

Each service has its own top-level folder: `user-service/`, `supplier-service/`,
`order-service/` and `credit-service/`. The frontend lives in `ui/` and HTTP routing
in `internal-gateway/`. See each folder's README for development instructions.

## Internal HTTP routing

Run `docker compose up --build` and open <http://127.0.0.1:4173>.

The UI and services route HTTP through `INTERNAL_GATEWAY_URL` (Compose:
`http://internal-gateway`). The [internal gateway](internal-gateway/README.md)
strips `/user-api/`, `/supplier-api/`, `/order-api/` or `/credit-api/` and forwards
to the matching service. Services enforce authentication and authorization.
The gateway is container-network-only; RabbitMQ and databases use separate connections.

## Deployment

Deployment is a full cutover: reset the application databases and RabbitMQ queues
before starting the new stack. Confirm the exact targets before deleting data,
including on hosted/shared infrastructure. Services create tables from current
ORM metadata; no in-place schema migration or legacy-message compatibility is
supported. Startup does not automatically delete databases or queues.

---

## AI Use Summary

**Tools:** ChatGPT (model details and usage dates documented in the AI usage log and source-file headers).

**Usage:**
- Generated initial React/Vite and FastAPI boilerplate and configuration.
- Assisted with frontend components, API integration, authentication, and administrative interfaces.
- Assisted with Credit Service implementation, SQLAlchemy models, RabbitMQ messaging, and credit operations based on provided specifications.
- Supported refactoring, debugging, testing, and documentation.

**Verification:** AI-assisted code was reviewed and modified by team members, with verification details recorded where applicable.

**Disclosure:** AI-influenced files contain attribution comments. Exact prompts, key responses, and usage scenarios are recorded in the [AI Usage Log](ai/usage-log.md).

---
