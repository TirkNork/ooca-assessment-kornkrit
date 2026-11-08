# Tools

Each file defines one tool: a Pydantic input schema (the field descriptions are what the model
sees) and a function that reads through a repository, so the same tool runs on the JSON mock or
Postgres. All tools are read-only and return JSON; errors come back as `{"error": ...}` for the
model to read instead of raising.

| Tool | Input | Returns | Used when |
|---|---|---|---|
| [`get_customer_history`](customer_history.py) | `customer_id` | Activity summary, past tickets | Every ticket |
| [`search_knowledge_base`](knowledge_base.py) | `query` (English), `top_k` 1–5 | Article id, title, content, score | Every ticket; once per issue |
| [`check_service_status`](service_status.py) | `region` | Real health, public status page, active incidents | Errors or downtime |
| [`get_billing_transactions`](billing.py) | `customer_id` | Subscription status, transactions | Payments, charges, upgrades |

The customer profile is not a tool: every ticket needs it, so `load_context` loads it up front.
