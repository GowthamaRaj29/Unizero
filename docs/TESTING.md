# Testing

## Executed

| Test | Expected | Actual | Status | Evidence |
|---|---|---|---|---|
| Backend suite | All tests pass | `2 passed` | PASS | `cd backend && python -m pytest -q` |
| Registration lifecycle | First user active admin; later user pending/inactive | Assertions passed | PASS | `backend/tests/test_auth_bootstrap.py` |
| Frontend production build | Vite build completes | Build completed | PASS | `cd frontend && npm run build` |
| Backend health | HTTP 200 | HTTP 200 | PASS | `http://127.0.0.1:8000/health` |
| AI health | HTTP 200 | HTTP 200 | PASS | `http://127.0.0.1:8001/health` |
| Frontend startup | HTTP 200 | HTTP 200 | PASS | `http://127.0.0.1:5173` |
| Gemini provider | Gemini selected and request succeeds | Health reported Gemini; synthetic explanation returned | PASS | AI health and `/explain-break` |
| AI-service suite | All tests pass | `155 passed, 1 skipped` | PASS | `cd ai-services && python -m pytest -q` |
| Clean browser setup | First admin and two approved roles | Completed through UI | PASS | `FINAL_VALIDATION_REPORT.md` |
| June real-data flow | Upload, review, mapping, override, undo | Completed through UI | PASS | June FA CSV + GL XML |
| Dynamic mismatch flow | Different dataset produces breaks | 38,686 breaks generated | PASS | July FA CSV + June GL XML |

## Not Yet Executed

- Backend-linked browser workflow from break investigation to report download.
- Clean virtual-environment installation.
- Backend run/break/approval persistence verification after a completed reconciliation.
- Negative API matrix and browser console capture.
- PDF/XLSX content inspection.

The application remains **NOT READY** until the final investigator, approver, audit, and report stages are executed against persisted backend records.
