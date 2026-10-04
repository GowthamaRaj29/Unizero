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
from gemini_client import GeminiAPIError, generate_text, normalize_model_json

logger = logging.getLogger("Unizero.explain")

MODEL = os.environ.get("GEMINI_EXPLAIN_MODEL", "gemini-3.5-flash")


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
        if client is not None or (
            not os.environ.get("GEMINI_API_KEY") and os.environ.get("ANTHROPIC_API_KEY")
        ):
            client = client or anthropic.Anthropic()
            response = client.messages.create(
                model=MODEL,
                max_tokens=300,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(user_payload)}],
            )
            raw_text = "".join(block.text for block in response.content if block.type == "text")
        else:
            raw_text = generate_text(_SYSTEM_PROMPT, json.dumps(user_payload), 300)
    except anthropic.APIError as exc:
        logger.error("AI explanation call failed for key=%s: %s", break_record.key, exc)
        raise ExplainServiceError(f"AI explanation call failed: {exc}") from exc
    except GeminiAPIError as exc:
        logger.warning("Gemini API call failed for key=%s: %s; using evidence-grounded fallback", break_record.key, exc)
        return Explanation(
            root_cause=f"Value discrepancy detected in field '{break_record.field}': '{break_record.value_a}' vs '{break_record.value_b}'.",
            confidence="medium",
            suggested_action=f"Verify source systems '{break_record.source_a}' and '{break_record.source_b}' for record key '{break_record.key}'.",
        )
    try:
        parsed = json.loads(normalize_model_json(raw_text))
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

RECONCILIATION_MODEL = os.environ.get("GEMINI_RCA_MODEL", MODEL)

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
    if client is None and not os.environ.get("GEMINI_API_KEY") and not os.environ.get("ANTHROPIC_API_KEY"):
        break_types = set(evidence.get("break_types") or [])
        if "MISSING_RECORD" in break_types:
            return ReconciliationRCA(
                root_cause="The transaction key is present in one source but missing from the other source.",
                confidence="high",
                supporting_evidence=["break_types=MISSING_RECORD", f"break_key={evidence.get('break_key')}"],
                suggested_action="Investigate the missing source record and confirm whether the transaction should be loaded.",
                raw_response="deterministic_rule",
            )

        return ReconciliationRCA(
            root_cause="The same reconciliation key has conflicting source values.",
            confidence="medium",
            supporting_evidence=[f"break_key={evidence.get('break_key')}", "source records contain differences"],
            suggested_action="Review the source values and confirm the authoritative record before approval.",
            raw_response="deterministic_rule",
        )

    try:
        if client is not None or (
            not os.environ.get("GEMINI_API_KEY") and os.environ.get("ANTHROPIC_API_KEY")
        ):
            client = client or anthropic.Anthropic()
            response = client.messages.create(
                model=RECONCILIATION_MODEL,
                max_tokens=400,
                system=_RECONCILIATION_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": json.dumps(evidence)}],
            )
            raw_text = "".join(block.text for block in response.content if block.type == "text")
        else:
            raw_text = generate_text(_RECONCILIATION_SYSTEM_PROMPT, json.dumps(evidence), 400)
    except anthropic.APIError as exc:
        logger.error(
            "Anthropic API call failed for break_key=%s: %s", evidence.get("break_key"), exc
        )
        raise ReconciliationRCAError(f"AI RCA call failed: {exc}") from exc
    except GeminiAPIError as exc:
        logger.warning("Gemini API call failed for break_key=%s: %s; using evidence-grounded fallback", evidence.get("break_key"), exc)
        break_types = set(evidence.get("break_types") or [])
        diffs = evidence.get("differences") or []
        present = evidence.get("present_in") or []
        missing = evidence.get("missing_in") or []
        if "MISSING_RECORD" in break_types:
            p_str = ", ".join([os.path.basename(str(p)) for p in present]) or "source reports"
            m_str = ", ".join([os.path.basename(str(m)) for m in missing]) or "other systems"
            return ReconciliationRCA(
                root_cause=f"Record {evidence.get('break_key')} exists in {p_str} but is missing in {m_str}.",
                confidence="high",
                supporting_evidence=[f"Present in: {p_str}", f"Missing in: {m_str}"],
                suggested_action=f"Cross-reference source ingestion for {m_str} and verify if transaction was settled.",
                raw_response="evidence_grounded_fallback",
            )
        elif diffs:
            d_desc = "; ".join([f"{d.get('field')} variance: {d.get('value_a')} vs {d.get('value_b')}" for d in diffs])
            return ReconciliationRCA(
                root_cause=f"Transaction values diverge across systems ({d_desc}).",
                confidence="medium",
                supporting_evidence=[f"Field differences: {d_desc}"],
                suggested_action="Review underlying journal entry with the trade confirmation ticket before approval.",
                raw_response="evidence_grounded_fallback",
            )
        else:
            return ReconciliationRCA(
                root_cause="UNKNOWN",
                confidence="low",
                supporting_evidence=[f"break_key={evidence.get('break_key')}"],
                suggested_action="Review transaction entries across source systems to confirm reason for break.",
                raw_response="evidence_grounded_fallback",
            )
    try:
        parsed = json.loads(normalize_model_json(raw_text))
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
