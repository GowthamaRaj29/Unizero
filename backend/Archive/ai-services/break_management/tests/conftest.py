import json
from types import SimpleNamespace

import pandas as pd
import pytest

from break_management import service
from break_management.permissions import PERMISSION_AUDIT_LOG
from field_mapping.auto_mapping import MappingConfig
from field_mapping.manual_mapping import COMMON, MAPPING_SESSIONS, MappingEntry, ManualMappingSession
from ingestion.workflow import SESSIONS, IngestionSession, IngestionStatus


@pytest.fixture(autouse=True)
def _clean_stores():
    """Every module here keeps an in-memory store -- reset all of them
    between tests so one test can never see another's data."""
    service.BREAKS.clear()
    MAPPING_SESSIONS.clear()
    SESSIONS.clear()
    PERMISSION_AUDIT_LOG.clear()
    yield
    service.BREAKS.clear()
    MAPPING_SESSIONS.clear()
    SESSIONS.clear()
    PERMISSION_AUDIT_LOG.clear()


def _entry(source, field_name, matched_source, matched_field, *, amount=False, method="exact_name"):
    return MappingEntry(
        source=source, field=field_name, matched_source=matched_source, matched_field=matched_field,
        score=1.0, category=COMMON, mapping_method=method,
        reason=f"'{field_name}' and '{matched_field}' match exactly.", is_amount_candidate=amount,
    )


def _fa_gl_entries():
    return [
        _entry("FA", "Amount", "GL", "Amount", amount=True),
        _entry("GL", "Amount", "FA", "Amount", amount=True),
        _entry("FA", "TransactionDate", "GL", "TransactionDate"),
        _entry("GL", "TransactionDate", "FA", "TransactionDate"),
        _entry("FA", "Currency", "GL", "Currency"),
        _entry("GL", "Currency", "FA", "Currency"),
        _entry("FA", "fa_key", "GL", "gl_account_id", method="crosswalk"),
    ]


@pytest.fixture
def two_source_setup():
    """Registers a fake FA/GL ingestion + mapping session with one clean
    row (T1) and one mismatched row (T2), and returns the mapping
    session id for analyze_breaks()."""
    fa_df = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "fa_key": "FA-001"},
        {"TransactionID": "T2", "Amount": 250.0, "TransactionDate": "2026-08-02", "Currency": "USD", "fa_key": "FA-002"},
    ])
    gl_df = pd.DataFrame([
        {"TransactionID": "T1", "Amount": 100.0, "TransactionDate": "2026-08-01", "Currency": "USD", "gl_account_id": "ACC001"},
        {"TransactionID": "T2", "Amount": 999.0, "TransactionDate": "2026-08-02", "Currency": "USD", "gl_account_id": "ACC002"},
    ])

    fa_session = IngestionSession(session_id="fa-sess", status=IngestionStatus.CLEAN, df=fa_df, metadata={})
    gl_session = IngestionSession(session_id="gl-sess", status=IngestionStatus.CLEAN, df=gl_df, metadata={})
    SESSIONS["fa-sess"] = fa_session
    SESSIONS["gl-sess"] = gl_session

    mapping_session = ManualMappingSession(
        mapping_session_id="map-1",
        ingestion_session_ids=["fa-sess", "gl-sess"],
        entries={e.key: e for e in _fa_gl_entries()},
        sources={"FA": "fa-sess", "GL": "gl-sess"},
        field_index={},
        config=MappingConfig(),
    )
    MAPPING_SESSIONS["map-1"] = mapping_session
    return "map-1"


class FakeAnthropicClient:
    """Mocks the tiny slice of the anthropic.Anthropic surface explain.py
    uses (client.messages.create(...).content -> text blocks), so tests
    never need ANTHROPIC_API_KEY or a real network call."""

    def __init__(self, reply: dict | str):
        self._reply = reply
        self.calls = []

        class _Messages:
            def __init__(self, outer):
                self._outer = outer

            def create(self, **kwargs):
                self._outer.calls.append(kwargs)
                text = self._outer._reply if isinstance(self._outer._reply, str) else json.dumps(self._outer._reply)
                return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])

        self.messages = _Messages(self)
