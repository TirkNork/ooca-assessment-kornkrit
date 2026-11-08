# Knowledge base

Twelve mock articles searched by `search_knowledge_base`, written to cover the sample tickets
and the eval test set.

## Articles

| ID | Title | What it says | Used by |
|---|---|---|---|
| [KB-001](KB-001-upgrading-your-plan.md) | Upgrading from Free to Pro | Pro is $29.99/month; each retry places another card hold, so contact support instead | T-1001 |
| [KB-012](KB-012-pending-and-duplicate-charges.md) | Pending or duplicate charges after a failed upgrade | Pending holds drop off in 3–5 business days; only billing can void or refund; a chargeback freezes the account | T-1001 |
| [KB-013](KB-013-refund-policy.md) | Refund policy | Full refund within 14 days; duplicate charges always refunded; 5–10 business days | T-1001, T-3001 |
| [KB-020](KB-020-themes-and-dark-mode.md) | Themes and dark mode | Dark theme rolling out to Pro/Enterprise; macOS app bug in 4.1.2 fixed in 4.1.3; no scheduled switching | T-1003, T-3009 |
| [KB-031](KB-031-http-500-errors.md) | Troubleshooting HTTP 500 errors | One user: clear cache, private window, extensions; several users: it is on our side | T-1002, T-2003 |
| [KB-032](KB-032-status-page-and-regional-incidents.md) | Status page and regional incidents | The status page can lag at the start of an incident; support checks internal monitoring | T-1002 |
| [KB-040](KB-040-pro-export-features.md) | Analytics Pro export features | Pro adds PDF/PPTX export (Share > Export); free gets watermarked PNG; Enterprise includes Pro | T-2001, T-3003, T-3020 |
| [KB-050](KB-050-enterprise-sla.md) | Enterprise SLA and priority support | 99.9% uptime; P1 first response in 30 minutes, 24/7; handled by engineering on-call | T-1002, T-2005 |
| [KB-060](KB-060-password-reset-and-2fa.md) | Resetting your password and 2FA | "Forgot password" link; lost 2FA device: backup codes or an admin reset | T-2004 |
| [KB-070](KB-070-team-members-and-seats.md) | Inviting team members and managing seats | Invite one by one or by CSV from Settings > Team; extra seats are prorated | T-2002, T-3005, T-3012, T-3016 |
| [KB-080](KB-080-suspicious-logins-and-account-security.md) | Suspicious logins and compromised accounts | Change password, sign out sessions, turn on 2FA; the security team reviews access | T-3007 |
| [KB-090](KB-090-data-export-and-deletion.md) | Exporting your data and deleting your account | Admins export CSV from Settings > Data; GDPR deletion by the privacy team within 30 days | T-3008, T-3022 |

**Left out on purpose** (the agent should route, not answer): Salesforce sync (T-3002),
partner program (T-3018), Kanban view (T-3021), menu language (T-3011), blank dashboards
(T-3010).

## Format

`KB-<number>-<slug>.md` with `id` and `title` front matter and a body of plain paragraphs. Only
`KB-*.md` files are loaded.

## How it is searched

- **File backend:** BM25, title weighted double.
- **Postgres backend:** paragraph chunks, vector + full-text search fused with RRF (min cosine
  0.3). Re-run `scripts/seed_db.py` after edits; only changed paragraphs are re-embedded.
- Articles up to 1,500 characters are returned whole; longer ones return matching paragraphs.
