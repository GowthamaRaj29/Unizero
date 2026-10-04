from io import BytesIO

import pandas as pd


def generate_excel(
    rows: list[dict]
):

    output = BytesIO()

    dataframe = pd.DataFrame(rows)

    with pd.ExcelWriter(
        output,
        engine="xlsxwriter"
    ) as writer:

        dataframe.to_excel(
            writer,
            index=False,
            sheet_name="Reconciliation"
        )

    output.seek(0)

    return output