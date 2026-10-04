"""
Requirement 6.1: AI Root Cause Analysis, orchestration layer.

Does not talk to Anthropic itself -- that stays in explain.py's
explain_reconciliation_break(), the single place that owns the prompt,
the client call, and the strict-JSON contract (shared with the existing
explain_break()/`/explain-break` path). This module's job is narrower:
turn a Break into bounded evidence (never the full dataset -- only this
break's own records/differences), call that function, and turn the
result into an RCAEntry appended to the break's history.

RCA is advisory only: nothing here writes to `records`, `differences`,
or any reconciled value, and nothing here changes `status` -- status
changes are exclusively a human action via service.py.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import anthropic

import explain
from break_management.models import Break, RCAEntry

logger = logging.getLogger("onerecon.break_management.rca")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_evidence(break_obj: Break) -> dict:
    """Only this break's own evidence -- its key, which systems it was
    found/missing in, the full per-source rows for the sources it WAS
    found in (a handful of fields for one transaction, not the dataset),
    and the differences already detected deterministically. No other
    break, and no unrelated rows, are ever included."""
    return {
        "break_key": break_obj.break_key,
        "key_field": break_obj.key_field,
        "break_types": break_obj.break_types,
        "present_in": break_obj.present_in,
        "missing_in": break_obj.missing_in,
        "records": break_obj.records,
        "differences": break_obj.differences,
    }


def run_rca(break_obj: Break, client: anthropic.Anthropic | None = None, actor: str = "system") -> RCAEntry:
    """
    Runs (or re-runs) RCA for one break and appends the result to its
    history -- never replaces a prior entry (see models.RCAEntry).
    Raises explain.ReconciliationRCAError on a genuine service failure
    (missing key, API error) so the API layer can surface a 503, exactly
    as the existing /explain-break endpoint does; it does not swallow
    that into a fabricated result.
    """
    evidence = _build_evidence(break_obj)
    result = explain.explain_reconciliation_break(evidence, client=client)

    entry = RCAEntry(
        rca_id=str(uuid.uuid4()),
        root_cause=result.root_cause,
        confidence=result.confidence,
        supporting_evidence=list(result.supporting_evidence),
        suggested_action=result.suggested_action,
        is_unknown=result.is_unknown,
        generated_at=_now(),
        model=explain.RECONCILIATION_MODEL,
    )
    break_obj.add_rca(entry, actor=actor)
    logger.info(
        "run_rca: break_id=%s rca_id=%s confidence=%s is_unknown=%s",
        break_obj.break_id, entry.rca_id, entry.confidence, entry.is_unknown,
    )
    return entry
