# OneRecon Frontend ↔ AI Services Integration

AI service is expected to run with:

    uvicorn app:app --reload

Default AI service URL:

    http://localhost:8000

The Vite development proxy maps:

    /ai-api/*  ->  http://localhost:8000/*

## Integrated Investigator endpoints

### Ingestion
- POST /ingestion/start
- GET /ingestion/{session_id}
- POST /ingestion/{session_id}/review

### Field Mapping
- POST /field-mapping/manual/session
- GET /field-mapping/manual/{mapping_session_id}
- POST /field-mapping/manual/{mapping_session_id}/override
- POST /field-mapping/manual/{mapping_session_id}/decision
- POST /field-mapping/manual/{mapping_session_id}/mapping-file
- POST /field-mapping/manual/{mapping_session_id}/reset
- POST /field-mapping/manual/{mapping_session_id}/undo
- POST /field-mapping/manual/{mapping_session_id}/preview
- GET /field-mapping/manual/{mapping_session_id}/validation
- POST /field-mapping/auto (API wrapper ready)

### Breaks / Investigation
- GET /breaks
- GET /breaks/summary
- GET /breaks/{break_id}
- POST /breaks/{break_id}/rca
- POST /breaks/{break_id}/status
- GET /breaks/{break_id}/lineage
- POST /breaks/{break_id}/investigator/cause

### Additional AI API wrappers
- GET /health
- POST /validate
- POST /map-fields
- POST /explain-break
- POST /breaks/analyze
- POST /breaks/aggregate/analyze
- POST /breaks/{break_id}/authorize
- POST /breaks/authorize/bulk
- POST /breaks/authorize/upload

## Important
The uploaded Swagger documentation lists these endpoints and schema names, but does not expose every request-model field. Therefore the frontend only auto-submits payloads whose shapes are already established by the existing integration or simple status/cause actions. The remaining endpoint wrappers accept a payload argument so they can be connected directly once the exact request schema is confirmed.

The current AI Swagger does not expose an evidence upload/download endpoint, so the Evidence page is not falsely connected to a nonexistent AI endpoint.
