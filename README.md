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
| Wei Hung | **User Service & Authentication:** Set up a reusable React/Vite frontend foundation with shared API utilities, components, and layouts, alongside the FastAPI User Service. Implemented user management, JWT-based session authentication, protected routes, role-based access control, and the Admin Manager Portal for granting/revoking administrator privileges.<br><br>**Credit Service:** Designed PostgreSQL wallet, reservation, and audit-log schemas; implemented automatic 100-credit allocation via `UserCreated` events and atomic reserve, release, and transfer operations with row locking and idempotency.<br><br>**Asynchronous Messaging:** Integrated RabbitMQ credit commands and success/rejection events, transactional outbox, reliable event publishing, duplicate-request handling, and persistent operation outcomes.<br><br>**Frontend & Deployment:** Developed credit audit-log interfaces, integrated service APIs, and configured Docker Compose and PostgreSQL database connections.<br><br>**Prototyping & Documentation:** Developed an draft UI prototype, proposed Figma Make for collaborative prototyping, and contributed to D3 Order Lifecycle Diagram, and demo preparation. |
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
