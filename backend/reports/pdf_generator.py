from io import BytesIO

from reportlab.lib.pagesizes import A4

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import getSampleStyleSheet


def generate_pdf(
    title: str,
    lines: list[str]
):

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=A4
    )

    styles = getSampleStyleSheet()

    content = [
        Paragraph(
            title,
            styles["Title"]
        ),
        Spacer(1, 20)
    ]

    for line in lines:

        content.append(
            Paragraph(
                line,
                styles["BodyText"]
            )
        )

        content.append(
            Spacer(1, 8)
        )

    document.build(content)

    output.seek(0)

    return output