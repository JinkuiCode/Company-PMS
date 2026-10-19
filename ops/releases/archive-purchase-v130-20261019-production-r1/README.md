# v1.3.0 production helper preparation

Application candidate 5c5baea and its fixed ZIP/bundle are unchanged. Real SQL R2 rehearsal completed successfully. This directory separates formal program maintenance from all preserved rehearsal evidence.

Formal approval is unset in pins.json. Do not run deploy/resume/rollback until the exact approved formal window reference and updated pin digest have been fixed and checked.

The controlled program allows only GET /api/reports/purchase/metadata in addition to the existing local-read acceptance paths, so the report's fields can be inspected without ERP connections. Existing route RBAC is retained. Report queries, candidates, export, ERP and SSO remain blocked. The actual metadata implementation uses local field definitions and scoped PMS product lines only.

The execution plan is docs/releases/2026-10-19-archive-purchase-v130-production-plan.md. No schema changes, grants, formal archive/draft writes, Git merge/push or real notifications are included. Preserve failures; never automatically retry, clean up or roll back.
