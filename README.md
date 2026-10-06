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
| Your Name | Your ownership |
| Your Name | Your ownership |

---

## Repository Structure

This repository follows a **one-service-per-folder** structure: each
microservice (`user-service/`, `supplier-service/`, `order-service/`,
`credit-service/`) lives in its own top-level folder.

```text
.
├── user-service/
├── supplier-service/
├── order-service/
├── credit-service/
├── internal-gateway/
├── <n2h-service>/
└── README.md
```

- Any **nice-to-have (N2H)** feature that warrants its own service should
  be added as an **additional folder** at the same level, following the
  same per-service structure.
- Files for agentic coding tools (e.g. agent configs, prompts, skills)
  may be added as needed, but must still **respect the
  one-service-per-folder skeleton** for core implementation.

## Internal HTTP routing

All HTTP calls between services use an explicitly configured
`INTERNAL_GATEWAY_URL`. Compose supplies `http://internal-gateway` for its known
Docker topology; applications do not assume a localhost destination. The [nginx internal
gateway](internal-gateway/README.md) routes `/user-api/` to user-service and
`/supplier-api/` to supplier-service, stripping only that service prefix.
Services keep their existing authentication and authorization responsibilities.
The UI also proxies API requests through this gateway.

For host-run development, explicitly configure the gateway origin
(`http://127.0.0.1:8080` with the default Compose mapping). Only gateway deployment
settings contain backend HTTP addresses, including for separate EC2 instances.
Bind addresses and DNS are configurable independently; RabbitMQ and databases
remain separate from HTTP routing.

---
