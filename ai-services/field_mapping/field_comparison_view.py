"""
Requirement 2, step 1 (continued): ties the field comparison view to
ingestion state. Pulls DataFrames directly from ingestion.workflow's
in-memory SESSIONS — never reloads a source file from disk, and never
builds a comparison for a session that hasn't cleared the human review
gate (only CLEAN or APPROVED sessions qualify).
"""

from __future__ import annotations

import logging

from field_mapping.comparison import build_field_profiles, serialize_field_profiles
from ingestion.workflow import IngestionStatus, WorkflowError, get_session

logger = logging.getLogger("onerecon.field_mapping.field_comparison_view")

_APPROVED_STATUSES = (IngestionStatus.CLEAN, IngestionStatus.APPROVED)


class FieldComparisonError(Exception):
    """Raised when a requested session can't be compared — unknown id,
    or a status that hasn't cleared the review gate yet."""


def get_field_comparison(session_ids: list[str]) -> dict:
    """
    session_ids: one or more ingestion session ids. Each becomes one
    entry in the returned "sources" list, in the order given — this is
    how multiple sources end up in a single response for the frontend to
    render as separate panels, without any new grouping/workflow concept
    needing to exist yet.
    """
    if not session_ids:
        raise FieldComparisonError("At least one ingestion session id is required")

    sources = []
    for session_id in session_ids:
        try:
            session = get_session(session_id)
        except WorkflowError as exc:
            raise FieldComparisonError(str(exc)) from exc

        if session.status not in _APPROVED_STATUSES:
            raise FieldComparisonError(
                f"Session {session_id} is not approved for comparison "
                f"(status={session.status.value}); only CLEAN or APPROVED sessions qualify"
            )

        profiles = build_field_profiles(session.df)
        sources.append(
            {
                "session_id": session.session_id,
                "name": session.metadata.get("source"),
                "fields": serialize_field_profiles(profiles),
            }
        )

    logger.info("get_field_comparison: built comparison for %d source(s)", len(sources))
    return {"sources": sources}