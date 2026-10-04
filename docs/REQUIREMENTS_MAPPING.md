# Requirements Mapping

| Requirement | Existing | Changed | Final Status | Evidence |
|---|---|---|---|---|
| Service startup | Three local services | Added Windows restart launcher | Implemented for local startup | `start-Unizero.bat`, README |
| First-user authentication | JWT and hashed passwords | Pending registration state corrected | Partially Implemented | `backend/auth/`, backend tests |
| Registration approval | Admin routes existed | Database-backed pending UI and actions | Implemented for current model | `backend/admin/router.py`, admin dashboard |
| Workflow persistence | CRUD API existed | Dashboard now creates and updates real workflow | Partially Implemented | `backend/workflows/`, investigator dashboard |
| File upload metadata | Data-source model/routes existed | Local upload and AI session linkage added | Partially Implemented | `backend/data_sources/`, dashboard |
| Validation gate | AI state machine exists | UI exposes GO_AHEAD | Partially Implemented | `ai-services/ingestion/`, dashboard |
| Dynamic mapping | AI mapping engine exists | UI consumes mapping API | Partially Implemented | field mapping services/page |
| Reconciliation persistence | Models exist | Full execution linkage not verified | Future integration | `backend/workflows/models.py` |
| Breaks and RCA | AI service and backend mirror exist | End-to-end run linkage not verified | Partially Implemented | `backend/ai_bridge/`, breaks UI |
| Investigation | Models/routes/UI exist | Real persisted break journey not verified | Partially Implemented | `backend/investigations/` |
| Evidence | Upload route existed | Added persisted evidence table/list and dynamic UI | Partially Implemented | `backend/investigations/`, investigator evidence page |
| Approval | Models/routes/UI exist | Approver screens now dynamic; lifecycle test remains | Partially Implemented | `backend/approvals/`, approver pages |
| Audit | Model/service exists | Workflow/upload/approval events added | Partially Implemented | `backend/audit/` |
| Reports | PDF/Excel endpoints exist | Actual report content not verified | Partially Implemented | `backend/reports/` |
| No runtime mocks | Some runtime fixtures existed | Approver/admin fixtures removed from active screens | Partially Implemented | hardcoding audit |
| Documentation | Master prompt and README existed | Required core documents added | Partially Implemented | `docs/` |
| End-to-end acceptance | Unit/smoke tests exist | No complete real-data run executed | Future integration | `FINAL_VALIDATION_REPORT.md` |
