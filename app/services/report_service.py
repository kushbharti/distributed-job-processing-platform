from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_styles = getSampleStyleSheet()


def _table(rows: list[tuple[str, str]]) -> Table:
    data = [
        [
            Paragraph(f"<b>{escape(label)}</b>", _styles["BodyText"]),
            Paragraph(escape(value), _styles["BodyText"]),
        ]
        for label, value in rows
    ]
    table = Table(data, colWidths=[45 * mm, 125 * mm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def build_report(
    destination: Path,
    *,
    filename: str,
    stats: dict,
    metadata: dict[str, str],
    keywords: list[str],
    summary: str,
) -> None:
    doc = SimpleDocTemplate(
        str(destination),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Report: {filename}",
        author="Distributed Job Processing Platform",
    )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    story = [
        Paragraph("Document Processing Report", _styles["Title"]),
        Paragraph(escape(filename), _styles["Heading3"]),
        Paragraph(f"Generated {generated}", _styles["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph("Statistics", _styles["Heading2"]),
        _table(
            [
                ("Pages", str(stats["pages"])),
                ("Words", f'{stats["words"]:,}'),
                ("Characters", f'{stats["characters"]:,}'),
                ("Reading time", f'about {stats["reading_minutes"]} min'),
            ]
        ),
        Spacer(1, 6 * mm),
        Paragraph("Summary", _styles["Heading2"]),
        Paragraph(escape(summary) or "No summary available.", _styles["BodyText"]),
        Spacer(1, 6 * mm),
        Paragraph("Top keywords", _styles["Heading2"]),
        Paragraph(escape(", ".join(keywords)) or "None found.", _styles["BodyText"]),
    ]

    if metadata:
        story += [
            Spacer(1, 6 * mm),
            Paragraph("Document metadata", _styles["Heading2"]),
            _table(list(metadata.items())),
        ]

    doc.build(story)