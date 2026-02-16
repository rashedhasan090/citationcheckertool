"""
Export citation check report to PDF, CSV, and JSON.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from .checker import CitationResult

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


def export_json(results: List[CitationResult], path: str) -> None:
    """Export results to JSON file."""
    data = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "total": len(results),
        "summary": _summary(results),
        "citations": [
            {
                "index": r.index,
                "status": r.status,
                "issues": r.issues,
                "suggestions": r.suggestions,
                "doi": r.doi,
                "url": r.url,
                "year": r.year,
                "authors": r.authors,
                "title": r.title,
                "doi_resolved": r.doi_resolved,
                "url_accessible": r.url_accessible,
                "raw_preview": (r.raw[:200] + "…") if len(r.raw) > 200 else r.raw,
            }
            for r in results
        ],
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def export_csv(results: List[CitationResult], path: str) -> None:
    """Export results to CSV file."""
    import csv
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "Index",
                "Status",
                "DOI",
                "Year",
                "Authors",
                "DOI Resolved",
                "URL Accessible",
                "Issues",
                "Suggestions",
                "Raw Preview",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.index,
                    r.status,
                    r.doi or "",
                    r.year or "",
                    "; ".join(r.authors) if r.authors else "",
                    r.doi_resolved,
                    r.url_accessible,
                    " | ".join(r.issues),
                    " | ".join(r.suggestions),
                    (r.raw[:150] + "…") if len(r.raw) > 150 else r.raw,
                ]
            )


def _summary(results: List[CitationResult]) -> dict:
    n = len(results)
    valid = sum(1 for r in results if r.status == "valid")
    warning = sum(1 for r in results if r.status == "warning")
    invalid = sum(1 for r in results if r.status == "invalid")
    fake = sum(1 for r in results if r.status == "suspected_fake")
    return {
        "valid": valid,
        "warning": warning,
        "invalid": invalid,
        "suspected_fake": fake,
        "total": n,
    }


def export_pdf(results: List[CitationResult], path: str) -> None:
    """Export results to PDF file. Requires reportlab."""
    if not HAS_REPORTLAB:
        raise ImportError("Report export to PDF requires: pip install reportlab")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        fontSize=16,
    )
    story = [Paragraph("Citation Check Report", title_style)]
    story.append(Paragraph(f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["Normal"]))
    story.append(Spacer(1, 0.2 * inch))
    summary = _summary(results)
    story.append(
        Paragraph(
            f"Total: {summary['total']} | Valid: {summary['valid']} | "
            f"Warning: {summary['warning']} | Suspected fake: {summary['suspected_fake']}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.3 * inch))
    data = [["#", "Status", "DOI", "Year", "Issues"]]
    for r in results:
        data.append(
            [
                str(r.index),
                r.status,
                (r.doi or "")[:30] + ("…" if r.doi and len(r.doi) > 30 else ""),
                r.year or "",
                "; ".join(r.issues)[:60] + ("…" if len(r.issues) > 0 and len("; ".join(r.issues)) > 60 else ""),
            ]
        )
    t = Table(data, colWidths=[0.4 * inch, 1.2 * inch, 1.8 * inch, 0.5 * inch, 2.6 * inch])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ]
        )
    )
    story.append(t)
    doc.build(story)
