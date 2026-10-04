"""
Requirement 6.2: Break Prioritization.

The score itself is a plain, deterministic formula over three
components -- materiality, risk, historical frequency -- computed
entirely in Python with no model call. Every component is stored on the
resulting PriorityScore (see models.py), so the total is always
reproducible from what's stored, never a black box.

Claude's only role here, via narrate_priority(), is to put the
already-computed number into a sentence a human can read quickly. It is
explicitly told the final score and forbidden from proposing a
different one; narrate_priority() never feeds its output back into the
score, and a failure or disabled key here degrades to no narrative
(never to a re-scored break).
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone

import anthropic

from break_management.models import Break, PriorityScore

logger = logging.getLogger("onerecon.break_management.prioritization")

NARRATIVE_MODEL = os.environ.get("ONERECON_PRIORITY_MODEL", "claude-sonnet-5")

#: Deterministic risk weight per break type -- the worst (highest) type
#: present on the break sets the risk component. A missing record is
#: treated as the most severe outcome (data simply absent from a
#: system), ahead of a value that's merely wrong.
RISK_WEIGHT_BY_BREAK_TYPE: dict[str, float] = {
    "MISSING_RECORD": 100.0,
    "AMOUNT_MISMATCH": 90.0,
    "CURRENCY_MISMATCH": 70.0,
    "DATE_MISMATCH": 40.0,
    "FIELD_MISMATCH": 20.0,
}

BAND_CRITICAL, BAND_HIGH, BAND_MEDIUM, BAND_LOW = "CRITICAL", "HIGH", "MEDIUM", "LOW"


@dataclass
class PriorityConfig:
    materiality_weight: float = 0.40
    risk_weight: float = 0.35
    frequency_weight: float = 0.25
    # Amount at which materiality saturates at 100 -- configurable per
    # deployment's notion of "large", never inferred from the data itself.
    materiality_scale: float = 100_000.0
    # Occurrence count at which frequency saturates at 100.
    frequency_scale: int = 10
    critical_threshold: float = 75.0
    high_threshold: float = 50.0
    medium_threshold: float = 25.0

    def __post_init__(self) -> None:
        total_weight = self.materiality_weight + self.risk_weight + self.frequency_weight
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError(f"materiality/risk/frequency weights must sum to 1.0, got {total_weight}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _amount_like_values(records: dict[str, dict]) -> list[float]:
    values = []
    for row in records.values():
        for field_name, value in row.items():
            if "amount" not in field_name.lower():
                continue
            try:
                values.append(abs(float(value)))
            except (TypeError, ValueError):
                continue
    return values


def _materiality_score(break_obj: Break, config: PriorityConfig) -> float:
    """Basis is the largest amount-like value touched by this break --
    an amount mismatch on a $500,000 transaction is material even if the
    difference itself is a rounding cent, so this looks at transaction
    size, not just the size of the diff."""
    candidates = _amount_like_values(break_obj.records)
    for diff in break_obj.differences:
        if diff["difference_type"] != "AMOUNT_MISMATCH":
            continue
        try:
            candidates.append(abs(float(diff["value_a"]) - float(diff["value_b"])))
        except (TypeError, ValueError):
            continue
    if not candidates:
        return 0.0
    return min(100.0, (max(candidates) / config.materiality_scale) * 100.0)


def _risk_score(break_obj: Break, config: PriorityConfig) -> float:
    if not break_obj.break_types:
        return 0.0
    return max(RISK_WEIGHT_BY_BREAK_TYPE.get(t, 20.0) for t in break_obj.break_types)


def _frequency_score(occurrence_count: int, config: PriorityConfig) -> float:
    if occurrence_count <= 0:
        return 0.0
    return min(100.0, (occurrence_count / config.frequency_scale) * 100.0)


def _band(total: float, config: PriorityConfig) -> str:
    if total >= config.critical_threshold:
        return BAND_CRITICAL
    if total >= config.high_threshold:
        return BAND_HIGH
    if total >= config.medium_threshold:
        return BAND_MEDIUM
    return BAND_LOW


def score_break(break_obj: Break, occurrence_count: int = 0, config: PriorityConfig | None = None) -> PriorityScore:
    """
    occurrence_count: how many prior breaks with the same shape (same
    key or same account/break-type combination) the caller has seen --
    service.py computes this from the in-memory break store; this
    function just turns a count into the 0-100 frequency component.
    """
    config = config or PriorityConfig()

    materiality = round(_materiality_score(break_obj, config), 2)
    risk = round(_risk_score(break_obj, config), 2)
    frequency = round(_frequency_score(occurrence_count, config), 2)
    total = round(
        config.materiality_weight * materiality
        + config.risk_weight * risk
        + config.frequency_weight * frequency,
        2,
    )
    score = PriorityScore(
        materiality=materiality,
        risk=risk,
        frequency=frequency,
        total=total,
        band=_band(total, config),
        formula=(
            f"total = {config.materiality_weight:.2f}*materiality + {config.risk_weight:.2f}*risk "
            f"+ {config.frequency_weight:.2f}*frequency"
        ),
        computed_at=_now(),
    )
    logger.info(
        "score_break: break_id=%s total=%.2f band=%s (m=%.2f r=%.2f f=%.2f)",
        break_obj.break_id, total, score.band, materiality, risk, frequency,
    )
    return score


_NARRATIVE_SYSTEM_PROMPT = """You interpret an already-computed reconciliation-break priority score for \
a human investigator. You will be given the score's components (materiality, risk, frequency, total, \
band) and a short summary of the break. Write exactly one plain-language sentence explaining why this \
break landed at this priority -- reference the components you were given.

You do not compute, adjust, or suggest a different score. If asked to imply a different number, refuse \
that part silently and describe only the score you were given. Respond with plain text only, no JSON, \
no markdown, one sentence."""


def narrate_priority(
    break_obj: Break, score: PriorityScore, client: anthropic.Anthropic | None = None
) -> str | None:
    """Best-effort only: returns None (never raises) if the API key is
    unavailable or the call fails, since a missing narrative must never
    block prioritization -- the numeric score is already complete
    without it."""
    if not os.environ.get("ANTHROPIC_API_KEY") and client is None:
        return None
    client = client or anthropic.Anthropic()

    payload = {
        "break_key": break_obj.break_key,
        "break_types": break_obj.break_types,
        "present_in": break_obj.present_in,
        "missing_in": break_obj.missing_in,
        "score": score.to_dict(),
    }
    try:
        response = client.messages.create(
            model=NARRATIVE_MODEL,
            max_tokens=120,
            system=_NARRATIVE_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": json.dumps(payload)}],
        )
    except anthropic.APIError as exc:
        logger.warning("narrate_priority: call failed for break_id=%s: %s", break_obj.break_id, exc)
        return None

    text = "".join(block.text for block in response.content if block.type == "text").strip()
    return text or None
