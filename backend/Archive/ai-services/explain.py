"""
Root-cause explanation: the second (and only other) AI touchpoint in the
architecture. Takes a break record plus its mapping/ingestion context and
returns one explanation. Nothing here holds state or calls itself — the
backend decides when to call this, once per break.

Requires ANTHROPIC_API_KEY in the environment. Never hardcode the key.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

import anthropic

logger = logging.getLogger("onerecon.explain")

MODEL = os.environ.get("ONERECON_EXPLAIN_MODEL", "claude-sonnet-5")


class ExplainServiceError(Exception):
    """Raised for any failure in the explanation call — callers should
    catch this and fall back to 'needs manual review', never crash."""

_SYSTEM_PROMPT = """You are a reconciliation break analyst for a bank. You will be given \
a break record: a transaction or aggregate that does not match across two or more \
financial systems, plus the field mapping that was used to compare them.

Respond with strict JSON only, matching this shape:
{"root_cause": "<one sentence, plain language>", \
"confidence": "high" | "medium" | "low", \
"suggested_action": "<one sentence, concrete next step>"}

Do not invent facts not present in the break record. If the data is insufficient to \
determine a cause, say so and set confidence to "low"."""


@dataclass
class BreakRecord:
    workflow_name: str
    source_a: str
    source_b: str
    field: str
    key: str
    value_a: object
    value_b: object
    mapping_context: dict = field(default_factory=dict)


@dataclass
class Explanation:
    root_cause: str
    confidence: str
    suggested_action: str
    raw_response: str


def explain_break(break_record: BreakRecord, client: anthropic.Anthropic | None = None) -> Explanation:
    if not os.environ.get("ANTHROPIC_API_KEY") and client is None:
        logger.error("ANTHROPIC_API_KEY not set — cannot call explanation service")
        raise ExplainServiceError("ANTHROPIC_API_KEY is not set in the environment")

    client = client or anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    user_payload = {
        "workflow": break_record.workflow_name,
        "comparing": f"{break_record.source_a} vs {break_record.source_b}",
        "field": break_record.field,
        "key": break_record.key,
        "value_in_source_a": break_record.value_a,
        "value_in_source_b": break_record.value_b,
        "mapping_context": break_record.mapping_context,
    }

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(user_payload)}],
        )
    except anthropic.APIError as exc:
        logger.error("Anthropic API call failed for key=%s: %s", break_record.key, exc)
        raise ExplainServiceError(f"AI explanation call failed: {exc}") from exc

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning("Non-JSON response from model for key=%s: %r", break_record.key, raw_text)
        return Explanation(
            root_cause="Could not parse AI response — needs manual review.",
            confidence="low",
            suggested_action="Investigator to review this break manually.",
            raw_response=raw_text,
        )

    logger.info(
        "explain_break: key=%s confidence=%s", break_record.key, parsed.get("confidence", "low")
    )
    return Explanation(
        root_cause=parsed.get("root_cause", ""),
        confidence=parsed.get("confidence", "low"),
        suggested_action=parsed.get("suggested_action", ""),
        raw_response=raw_text,
    )


# ---------------------------------------------------------------------------
# Requirement 6.1 (break_management): reconciliation-break RCA.
#
# explain_break()/BreakRecord above are single-field, single-source-pair --
# too narrow for a reconciliation.matcher.ReconciliationBreak, which can
# span 3 sources (FA/MA/GL) and several differing fields for one
# transaction key at once. Rather than force that shape or duplicate the
# call/parse/error-handling machinery above, this reuses it: same env-key
# check, same strict-JSON contract, same "never invent, never crash"
# fallback -- only the payload shape and the system prompt differ, and the
# prompt here is stricter about literally returning "UNKNOWN" per
# Requirement 6.1. explain_break() itself is untouched by this addition.
# ---------------------------------------------------------------------------

RECONCILIATION_MODEL = os.environ.get("ONERECON_RCA_MODEL", MODEL)

_RECONCILIATION_SYSTEM_PROMPT = """You are a reconciliation break analyst for a bank. You will be given \
structured evidence for ONE break: a transaction key, which financial systems it was found in or \
missing from, and -- for every field two of those systems disagree on -- the field name, both \
values, why the two fields were judged comparable, and what kind of mismatch it is (amount, date, \
currency, or a missing record).

Respond with strict JSON only, matching this shape:
{"root_cause": "<one or two sentences, plain language, e.g. 'FA includes inter-departmental entries \
excluded in RR.'>", "confidence": "high" | "medium" | "low", "supporting_evidence": ["<short pointer \
to which specific field/value in the input supports this>", ...], "suggested_action": "<one sentence, \
concrete next step for a human investigator>"}

Hard rules:
- Use ONLY the evidence you are given. Never infer, assume, or state a fact that is not literally \
present in the input (no guessing at upstream systems, timing, or business processes not shown).
- If the evidence does not clearly support a specific cause, set "root_cause" to exactly "UNKNOWN" \
(that literal string) and "confidence" to "low" -- do not speculate to fill the field.
- This is advisory analysis only. Never state or imply that the break has been, or should be \
automatically, resolved, corrected, or that any data was or should be modified. Only a human \
investigator changes break status or financial data.
- Keep "supporting_evidence" grounded in the exact field names/values given; do not restate the whole \
input."""


class ReconciliationRCAError(ExplainServiceError):
    """Raised for any failure in the reconciliation-break RCA call --
    callers should catch this and fall back to 'needs manual review',
    exactly as with ExplainServiceError."""


@dataclass
class ReconciliationRCA:
    root_cause: str
    confidence: str
    supporting_evidence: list
    suggested_action: str
    raw_response: str

    @property
    def is_unknown(self) -> bool:
        return self.root_cause.strip().upper() == "UNKNOWN"


def explain_reconciliation_break(
    evidence: dict, client: anthropic.Anthropic | None = None
) -> ReconciliationRCA:
    """
    evidence: a JSON-safe dict built from exactly one
    reconciliation.matcher.ReconciliationBreak (see
    break_management/rca.py for how it's assembled) -- never the full
    dataset, never other breaks. Only the break's own key, records, and
    differences are sent to the model.
    """
    if not os.environ.get("ANTHROPIC_API_KEY") and client is None:
        logger.error("ANTHROPIC_API_KEY not set — cannot call reconciliation RCA service")
        raise ReconciliationRCAError("ANTHROPIC_API_KEY is not set in the environment")

    client = client or anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    try:
        response = client.messages.create(
            model=RECONCILIATION_MODEL,
            max_tokens=400,
            system=_RECONCILIATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(evidence)}],
        )
    except anthropic.APIError as exc:
        logger.error(
            "Anthropic API call failed for break_key=%s: %s", evidence.get("break_key"), exc
        )
        raise ReconciliationRCAError(f"AI RCA call failed: {exc}") from exc

    raw_text = "".join(block.text for block in response.content if block.type == "text")
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        logger.warning(
            "Non-JSON RCA response for break_key=%s: %r", evidence.get("break_key"), raw_text
        )
        return ReconciliationRCA(
            root_cause="UNKNOWN",
            confidence="low",
            supporting_evidence=[],
            suggested_action="Investigator to review this break manually.",
            raw_response=raw_text,
        )

    logger.info(
        "explain_reconciliation_break: break_key=%s confidence=%s",
        evidence.get("break_key"), parsed.get("confidence", "low"),
    )
    return ReconciliationRCA(
        root_cause=parsed.get("root_cause") or "UNKNOWN",
        confidence=parsed.get("confidence", "low"),
        supporting_evidence=parsed.get("supporting_evidence", []),
        suggested_action=parsed.get("suggested_action", ""),
        raw_response=raw_text,
    )
