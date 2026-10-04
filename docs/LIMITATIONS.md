# Limitations

## Fully Implemented

- Local Windows service restart script.
- Password hashing and JWT authentication.
- First-user admin bootstrap.
- Inactive pending registration workflow and database-backed admin approval UI.
- Basic workflow and source metadata persistence.
- Investigation evidence persistence and listing.
- Existing AI ingestion, validation, mapping, break, RCA, and report modules remain available.

## Partially Implemented

- AI ingestion and mapping sessions are process-memory state, not database state.
- Workflow uploads are linked to AI session IDs, but reconciliation run persistence is not connected end to end.
- Break mirroring does not yet guarantee complete run/source-value linkage.
- Investigation and approval APIs exist, but one complete real break lifecycle has not been demonstrated.
- Reports exist, but actual generated files have not been inspected against the full required contents.
- Rejected users and disabled users are both represented by `is_active=False`; an explicit registration status is still needed to distinguish them.

## Not Implemented or Unverified

- Clean-environment installation and a fresh database acceptance run.
- Dynamic two-dataset replacement test.
- Browser console/network zero-warning validation.
- Complete report download/content verification.
- Full lifecycle audit coverage for every required event.

## Future Enterprise Capabilities

- Durable AI session and run repositories.
- Database migrations instead of create-all startup initialization.
- Object storage and antivirus scanning for uploads.
- Background jobs, multi-user workflow ownership, and production observability.
