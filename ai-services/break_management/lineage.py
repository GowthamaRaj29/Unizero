"""
Requirement 6.3: Investigation / Transaction Lineage.

Purely structural and deterministic -- no AI, no new data access. A
Break's `records` already hold the full per-source row (including each
source's own account/customer key -- fa_key, ma_customer_key,
gl_account_id -- since reconciliation.matcher stores the whole row, not
just the compared fields), so building the lineage graph is just a
reshape of what the break already carries. The frontend owns rendering;
this only returns structured nodes and edges, as the requirement asks.

Shape: one central "transaction" hub node for the break key, one spoke
node per source (whether the record was found there or not), and one
edge per detected difference directly between the two disagreeing
source nodes -- so a viewer can see both "where did this transaction
appear" and "where exactly do the systems disagree" in the same graph.
"""

from __future__ import annotations

from break_management.models import Break, LineageEdge, LineageNode

HUB_SOURCE = "RECONCILIATION"
RECORDED_IN = "recorded_in"
MISSING_FROM = "missing_from"


def build_lineage(break_obj: Break) -> dict:
    hub_id = f"TXN:{break_obj.break_key}"
    nodes: list[LineageNode] = [
        LineageNode(
            node_id=hub_id,
            source=HUB_SOURCE,
            label=f"Transaction {break_obj.break_key}",
            attributes={"key_field": break_obj.key_field, "break_types": break_obj.break_types},
        )
    ]
    edges: list[LineageEdge] = []

    for source in break_obj.present_in:
        node_id = f"{source}:{break_obj.break_key}"
        nodes.append(
            LineageNode(
                node_id=node_id,
                source=source,
                label=f"{source} record",
                attributes=break_obj.records.get(source, {}),
            )
        )
        edges.append(LineageEdge(from_id=hub_id, to_id=node_id, relationship=RECORDED_IN))

    for source in break_obj.missing_in:
        node_id = f"{source}:{break_obj.break_key}:missing"
        nodes.append(
            LineageNode(node_id=node_id, source=source, label=f"Not found in {source}", attributes={})
        )
        edges.append(LineageEdge(from_id=hub_id, to_id=node_id, relationship=MISSING_FROM))

    for diff in break_obj.differences:
        edges.append(
            LineageEdge(
                from_id=f"{diff['source_a']}:{break_obj.break_key}",
                to_id=f"{diff['source_b']}:{break_obj.break_key}",
                relationship=diff["difference_type"],
                attributes={
                    "field_a": diff["field_a"], "value_a": diff["value_a"],
                    "field_b": diff["field_b"], "value_b": diff["value_b"],
                    "mapping_reason": diff["mapping_reason"],
                },
            )
        )

    return {"nodes": [n.to_dict() for n in nodes], "edges": [e.to_dict() for e in edges]}
