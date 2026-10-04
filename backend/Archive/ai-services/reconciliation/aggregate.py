"""
Bugfix #10 (part 2): business_rules.txt's R10 rule
("AGGREGATE|SUM|KEYS=gl_account_id|Aggregate Amount per key across the
three reports.") was never actually implemented anywhere:

  - rules_engine.py explicitly parses AGGREGATE and then skips it --
    "Meta rule types ... describe workflow-level configuration, not
    per-row checks ... they belong to the ingestion/mapping stage, not
    here."
  - field_mapping/crosswalk.py reads only the crosswalk file's header
    (column names) and says row-level linkage is "a natural extension
    once the reconciliation/matching engine exists to consume it" --
    deferred, not done.

reconciliation/matcher.py (the engine both of those were waiting on)
only reconciles at transaction level. This module is the account-level
counterpart R10 actually asks for: sum the reconciliation-amount field
per real-world account -- accounts linked across FA/MA/GL by the
crosswalk file's own ROWS, not just its header -- and flag accounts
whose per-source totals disagree.

Deterministic, no AI. Reuses field_mapping.crosswalk.load_crosswalk_fields
(header only) to find each source's own account-key column generically,
same as reconciliation/matcher.py does for field pairs; never hardcodes
"gl_account_id"/"fa_key"/"ma_customer_key". Reading the crosswalk file's
full rows (not just its header) is new -- crosswalk.py deliberately
doesn't do that, by its own documented scope -- so it lives here instead
of being bolted onto that module.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from field_mapping.crosswalk import CrosswalkError, load_crosswalk_fields
from field_mapping.manual_mapping import ManualMappingSession

logger = logging.getLogger("onerecon.reconciliation.aggregate")


class AggregateReconciliationError(Exception):
    """Raised for invalid aggregate-reconciliation input -- unreadable
    crosswalk file, or fewer than two sources with a resolvable
    account-key column and amount field."""


@dataclass
class AggregateBreak:
    account: dict  # the full crosswalk row identifying this account across sources
    totals: dict[str, float]  # source -> summed reconciliation-amount for this account
    max_difference: float
    detected_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return {
            "account": self.account,
            "totals": {s: round(v, 2) for s, v in self.totals.items()},
            "max_difference": round(self.max_difference, 2),
            "detected_at": self.detected_at,
        }


def _load_crosswalk_rows(path: str | Path) -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        raise CrosswalkError(f"Crosswalk file not found: {file_path}")
    try:
        df = pd.read_csv(file_path)
    except (pd.errors.ParserError, OSError, UnicodeDecodeError) as exc:
        raise CrosswalkError(f"Could not read crosswalk file {file_path}: {exc}") from exc
    return df.to_dict("records")


def _account_key_column(df_columns, crosswalk_fields: set[str]) -> str | None:
    """The one column of this source that is also a crosswalk-linked
    column -- i.e. this source's own account-key field. None if there
    isn't exactly one such column (missing, or ambiguous)."""
    matches = [c for c in df_columns if c in crosswalk_fields]
    return matches[0] if len(matches) == 1 else None


def _amount_field_for_source(session: ManualMappingSession, source: str) -> str | None:
    """The YELLOW (reconciliation-amount) field already identified for
    this source by field_mapping -- reused, not re-derived."""
    for entry in session.entries.values():
        if entry.source == source and entry.is_amount_candidate:
            return entry.field
    return None


def reconcile_aggregates(
    session: ManualMappingSession,
    dataframes: dict[str, pd.DataFrame],
    crosswalk_path: str | Path,
    tolerance: float = 0.01,
) -> list[AggregateBreak]:
    """
    Implements business_rules.txt's R10: for each account named in the
    crosswalk file, sums every resolvable source's reconciliation-amount
    field for that account's rows and flags accounts whose per-source
    totals disagree by more than `tolerance`. An account present in
    fewer than two resolvable sources is skipped -- there's nothing to
    compare it against.
    """
    crosswalk_fields = load_crosswalk_fields(crosswalk_path)
    crosswalk_rows = _load_crosswalk_rows(crosswalk_path)

    sources = [s for s in session.sources if s in dataframes]

    key_columns: dict[str, str] = {}
    per_source_sums: dict[str, dict[str, float]] = {}
    for source in sources:
        df = dataframes[source]
        key_col = _account_key_column(df.columns, crosswalk_fields)
        amount_field = _amount_field_for_source(session, source)
        if key_col is None or amount_field is None or amount_field not in df.columns:
            logger.info(
                "reconcile_aggregates: source=%s skipped (key_column=%s amount_field=%s)",
                source, key_col, amount_field,
            )
            continue
        amounts = pd.to_numeric(df[amount_field], errors="coerce")
        sums = amounts.groupby(df[key_col]).sum()
        key_columns[source] = key_col
        per_source_sums[source] = {str(k): float(v) for k, v in sums.items()}

    resolvable_sources = list(per_source_sums)
    if len(resolvable_sources) < 2:
        raise AggregateReconciliationError(
            "reconcile_aggregates requires at least two sources with a resolvable account-key "
            f"column and amount field; resolved only {resolvable_sources}"
        )

    breaks: list[AggregateBreak] = []
    for row in crosswalk_rows:
        totals: dict[str, float] = {}
        for source in resolvable_sources:
            key_value = row.get(key_columns[source])
            if key_value is None:
                continue
            total = per_source_sums[source].get(str(key_value))
            if total is not None:
                totals[source] = total

        if len(totals) < 2:
            continue  # this account isn't present in enough resolvable sources to compare

        max_difference = max(totals.values()) - min(totals.values())
        if max_difference > tolerance:
            breaks.append(AggregateBreak(account=row, totals=totals, max_difference=max_difference))

    logger.info(
        "reconcile_aggregates: resolvable_sources=%s accounts_checked=%d breaks=%d",
        resolvable_sources, len(crosswalk_rows), len(breaks),
    )
    return breaks
