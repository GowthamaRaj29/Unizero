# Unizero Implementation

## Existing Work Reused

The implementation preserves the existing FastAPI backend, SQLite models, AI-service ingestion/validation/mapping/reconciliation modules, React UI, and reporting endpoints.

## Changes Made

- Added `start-Unizero.bat` for repeatable Windows service restart.
- Corrected registration approval state: first user is active admin; later registrations are inactive until approval.
- Connected admin registration approvals to the database and removed the admin page's static requests.
- Connected approver dashboard and approval history to backend APIs.
- Persisted workflow creation before ingestion instead of creating a browser-only `Date.now()` workflow.
- Stored local uploaded source files under the workflow and linked AI ingestion session IDs to data-source records.
- Added workflow status updates and lifecycle audit records.
- Added persisted investigation evidence records and a database-backed evidence screen.
- Corrected the Vite AI proxy to target port `8001` and fixed multipart workflow upload query parameters.
- Persisted a local development JWT secret so backend restarts do not invalidate active sessions.
- Added deterministic rule-based RCA when no external AI key is configured.
- Enabled Gemini from the ignored `ai-services/.env`; verified a live explanation request and kept the shareable example key-free.
- Replaced deprecated Pydantic/FastAPI patterns and added `.env.example`.
- Added the required gap analysis and validation documentation.

## Current Integration Boundary

The browser still calls the standalone AI service for ingestion and field mapping. The backend stores workflow and data-source metadata and mirrors selected break records, but a complete durable mapping/run/result lifecycle has not yet been proven.

## Security and Configuration

Runtime secrets come from `.env` when supplied; otherwise a local `.jwt-secret` is generated once for development and ignored by Git. `.env` is ignored and `.env.example` contains no secret. Passwords are hashed before persistence and inactive users cannot authenticate.

## Validation Evidence

- Backend tests: `python -m pytest -q` -> `2 passed`.
- Frontend build: `npm run build` -> passed.
- Live health checks: backend, AI service, and frontend returned HTTP 200 after restart.
- Browser acceptance run: first admin setup, investigator/approver approval, real June FA/GL ingestion, review gate, mapping validation, manual override/undo, and July/June break generation were exercised.
- Remaining warning: external ReportLab `ast.NameConstant` deprecation warning.

## Not Yet Demonstrated

A real user-to-report browser/API run, durable reconciliation-run persistence, approval linkage, clean virtual-environment installation, and report content verification remain open. See `LIMITATIONS.md` and `FINAL_VALIDATION_REPORT.md`.
