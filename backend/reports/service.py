from reports.pdf_generator import generate_pdf
from reports.excel_generator import generate_excel


def create_pdf_report(
    workflow_name,
    period,
    breaks
):

    lines = [
        f"Workflow: {workflow_name}",
        f"Period: {period}",
        f"Total Breaks: {len(breaks)}"
    ]

    for item in breaks:

        lines.append(
            f"Break {item.id}: "
            f"{item.status} | Key: {item.reconciliation_key} | "
            f"Type: {item.break_type} | RCA: {item.ai_explanation or 'Pending'}"
        )

    return generate_pdf(
        "OneRecon Reconciliation Report",
        lines
    )


def create_excel_report(
    breaks
):

    rows = []

    for item in breaks:

        rows.append({
            "Break ID": item.id,
            "Workflow ID": item.workflow_id,
            "Run ID": item.run_id,
            "Reconciliation Key": item.reconciliation_key,
            "Break Type": item.break_type,
            "Status": item.status,
            "Field": item.field,
            "Source A": item.source_a_value,
            "Source B": item.source_b_value,
            "Difference": item.difference
            ,"RCA": item.ai_explanation,
        })

    return generate_excel(rows)