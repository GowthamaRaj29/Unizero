# Unizero Implementation Gap Analysis

Updated: 2026-09-20

This is an evidence-based status of the current repository and the browser/API validation performed with the supplied FA/GL datasets.

| Area | Current implementation | Current status | Next action |
|---|---|---|---|
| Startup | `start-Unizero.bat` stops ports `5173/5174/8000/8001` and starts all services | PASS | Add clean-install automation |
| Authentication | JWT, hashing, first-user admin bootstrap, inactive pending users, persistent local JWT secret | PASS for tested roles | Add broader negative authorization tests |
| Registration approval | Database-backed pending list, approve/reject UI and audit events | PASS | Add explicit registration status separate from disabled users |
| Roles | Admin, Investigator, Approver dependencies and UI routes | PARTIAL | Exercise every forbidden operation with negative tests |
| Workflow | Dashboard creates real backend workflow and updates status | PASS for creation/status | Add workflow run history and persisted run linkage |
| Upload | Browser local files are stored as data sources and sent to AI ingestion | PASS for CSV/XML | Persist validation decisions and source-level audit events |
| Validation gate | AI validation can pause sessions; UI exposes Go Ahead | PASS in browser | Persist AI session/review details in backend tables |
| Field mapping | Dynamic AI mapping, validation, manual override, undo | PASS in browser | Store mapping session/results against workflow in backend |
| Reconciliation | AI matcher generates real results/breaks from different datasets | PARTIAL | Create backend `ReconciliationRun` and result records for every execution |
| Break management | Real July/June mismatch produced 38,686 breaks in AI service | PARTIAL | Mirror frontend-triggered breaks through backend with workflow/run IDs |
| RCA | Gemini live explanation works; deterministic fallback works without a key | PASS at service/unit level | Complete live RCA on a bounded break after backend mirroring |
| Investigation | Break detail, lineage, finding fields and submit UI exist | PARTIAL | Link investigation creation to backend persisted break records |
| Approval | Dynamic approver dashboard/history and approval APIs exist | PARTIAL | Feed approvals from persisted investigations created by the real run |
| Audit | Registration/workflow/upload/evidence/approval events are stored | PARTIAL | Add validation, mapping, reconciliation, break, investigation and report events |
| Evidence | Persisted evidence table, upload/list API, dynamic Evidence screen | PASS at API/UI level | Add download endpoint and browser upload verification |
| Reporting | PDF/Excel endpoints exist | NOT VERIFIED end to end | Generate/download/open files containing run, breaks, RCA, approval and audit data |
| Runtime mocks | Admin/approver runtime mocks removed; hardcoding search clean in active backend/frontend | PASS for audited patterns | Review remaining archived and unused fixtures separately |
| Secrets | Runtime key in ignored `ai-services/.env`; examples are key-free | PASS configuration | Rotate any key previously committed/shared in an example file |
| Documentation | Required core docs and validation report exist | PASS documentation set | Keep statuses synchronized with executed evidence |
| Clean persistence | Current clean test DB contains 3 users, 4 workflows, 6 sources, 12 audit rows | PARTIAL | Verify completed run/break/approval/report persistence after restart |

## Verified Browser Journey

1. Fresh first-user registration created the active admin.
2. Investigator and Approver registrations were pending until admin approval.
3. June FA CSV and June GL XML were uploaded through the browser.
4. Both sources required and passed human Go Ahead.
5. Mapping validation, manual override, duplicate alert, and undo were exercised.
6. July FA CSV with June GL XML produced a different dynamic mismatch run and 38,686 breaks.
7. Break list and lineage loaded for the real mismatch run.

## Current Blocking Integration Gap

The frontend currently calls AI break analysis directly. The backend approval workflow expects backend-persisted investigations and breaks. These two paths must be unified around `workflow_id`, `run_id`, and persisted break IDs before the full investigator-to-approver-to-report acceptance test can pass.

## Readiness

**NOT READY** for final MVP acceptance until backend-linked run/break/investigation/approval/report persistence is executed and verified after restart.
