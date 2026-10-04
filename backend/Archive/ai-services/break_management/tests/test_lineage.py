from break_management.lineage import build_lineage
from break_management.models import Break
from reconciliation.matcher import FieldDifference, ReconciliationBreak


def test_lineage_includes_hub_and_one_node_per_source():
    rb = ReconciliationBreak(
        break_key="T1", key_field="TransactionID",
        present_in=["FA", "GL"], missing_in=["MA"],
        records={
            "FA": {"TransactionID": "T1", "Amount": 100.0},
            "GL": {"TransactionID": "T1", "Amount": 105.0},
        },
        differences=[
            FieldDifference(
                source_a="FA", field_a="Amount", value_a=100.0,
                source_b="GL", field_b="Amount", value_b=105.0,
                difference_type="AMOUNT_MISMATCH", mapping_reason="numeric",
            )
        ],
        mapping_session_id="map-1",
    )
    br = Break.from_reconciliation_break(rb)

    lineage = build_lineage(br)

    node_ids = {n["id"] for n in lineage["nodes"]}
    assert "TXN:T1" in node_ids
    assert "FA:T1" in node_ids
    assert "GL:T1" in node_ids
    assert "MA:T1:missing" in node_ids
    assert len(lineage["nodes"]) == 4


def test_lineage_edges_cover_hub_spokes_and_the_difference():
    rb = ReconciliationBreak(
        break_key="T1", key_field="TransactionID",
        present_in=["FA", "GL"], missing_in=["MA"],
        records={"FA": {"TransactionID": "T1"}, "GL": {"TransactionID": "T1"}},
        differences=[
            FieldDifference(
                source_a="FA", field_a="Amount", value_a=100.0,
                source_b="GL", field_b="Amount", value_b=105.0,
                difference_type="AMOUNT_MISMATCH", mapping_reason="numeric",
            )
        ],
        mapping_session_id="map-1",
    )
    br = Break.from_reconciliation_break(rb)

    lineage = build_lineage(br)
    edges = lineage["edges"]

    hub_edges = [e for e in edges if e["from"] == "TXN:T1"]
    assert {e["to"] for e in hub_edges} == {"FA:T1", "GL:T1", "MA:T1:missing"}
    assert {e["relationship"] for e in hub_edges} == {"recorded_in", "missing_from"}

    diff_edges = [e for e in edges if e["relationship"] == "AMOUNT_MISMATCH"]
    assert len(diff_edges) == 1
    assert diff_edges[0]["from"] == "FA:T1"
    assert diff_edges[0]["to"] == "GL:T1"
    assert diff_edges[0]["attributes"]["value_a"] == 100.0
    assert diff_edges[0]["attributes"]["value_b"] == 105.0


def test_lineage_with_no_differences_still_links_all_present_sources():
    rb = ReconciliationBreak(
        break_key="T1", key_field="TransactionID",
        present_in=["FA"], missing_in=["GL", "MA"],
        records={"FA": {"TransactionID": "T1"}},
        differences=[],
        mapping_session_id="map-1",
    )
    br = Break.from_reconciliation_break(rb)

    lineage = build_lineage(br)

    assert len(lineage["nodes"]) == 4  # hub + FA + GL(missing) + MA(missing)
    assert len(lineage["edges"]) == 3  # hub -> each of the three spokes
