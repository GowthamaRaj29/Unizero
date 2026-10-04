"""
Requirement 2, step 2 (part 2): crosswalk evidence for Automated Field
Mapping.

A crosswalk file (e.g. join_map.txt) doesn't map *field names* by
itself -- its header row names the columns from each system that key
the same real-world entity together. In this dataset that's exactly
business_rules.txt's R09: "GL:gl_account_id;MA:ma_customer_key;FA:fa_key".
Any field in an ingested source whose name matches one of those header
columns exactly is an authoritative cross-system key -- no embedding or
value scoring needed, the crosswalk file itself is the evidence.

Scope, stated plainly: this reads and trusts the crosswalk's *column
names* only (via nrows=0 -- the header, nothing else). It does not
cross-check that the actual sample values of two candidately-linked
fields appear together in the same crosswalk row; that row-level
verification is a natural extension once the reconciliation/matching
engine exists to consume it, but is out of scope for field *mapping*.
This function never reads a source's ingested business data file --
only the small crosswalk file itself -- consistent with not reloading
raw files that ingestion.py already parsed.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger("Unizero.field_mapping.crosswalk")


class CrosswalkError(Exception):
    """Raised when a crosswalk path is given but can't be read."""


def load_crosswalk_fields(path: str | Path) -> set[str]:
    """Returns the set of column names declared by the crosswalk file's header."""
    file_path = Path(path)
    if not file_path.exists():
        raise CrosswalkError(f"Crosswalk file not found: {file_path}")
    try:
        header_df = pd.read_csv(file_path, nrows=0)
    except (pd.errors.ParserError, OSError, UnicodeDecodeError) as exc:
        raise CrosswalkError(f"Could not read crosswalk file {file_path}: {exc}") from exc

    fields = set(header_df.columns)
    logger.info("load_crosswalk_fields: %s -> %d field(s): %s", file_path, len(fields), sorted(fields))
    return fields
