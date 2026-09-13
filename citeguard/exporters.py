import csv
import json
from pathlib import Path

from .models import VerificationResult


def flatten(r: VerificationResult) -> dict:
    return {
        "index": r.citation.index,
        "assessment": r.assessment,
        "confidence": r.confidence,
        "cited_title": r.citation.title or "",
        "cited_doi": r.citation.doi or "",
        "matched_title": r.matched.title if r.matched else "",
        "matched_doi": r.matched.doi if r.matched else "",
        "matched_year": r.matched.year if r.matched else "",
        "matched_source": r.matched.source if r.matched else "",
        "retracted": bool(r.matched and r.matched.is_retracted),
        "support_score": r.support_score if r.support_score is not None else "",
        "notices": " | ".join(r.notices),
        "evidence_sources": ", ".join(r.evidence_sources),
        "raw_citation": r.citation.raw,
    }


def export_json(results, path):
    Path(path).write_text(json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False), encoding="utf-8")


def export_csv(results, path):
    rows = [flatten(r) for r in results]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["index"])
        w.writeheader()
        w.writerows(rows)


def export_pdf(results, path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(path), pagesize=letter)
    width, height = letter
    y = height - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "CiteGuard Verification Report")
    y -= 28
    c.setFont("Helvetica", 9)
    for r in results:
        lines = [f"[{r.citation.index}] {r.assessment.upper()} — {r.confidence}%", r.citation.raw[:115],
                 f"Match: {(r.matched.title if r.matched else 'None')[:105]}", f"Sources: {', '.join(r.evidence_sources) or 'none'}"]
        if r.notices:
            lines.append("Notices: " + "; ".join(r.notices)[:110])
        for line in lines:
            if y < 60:
                c.showPage()
                c.setFont("Helvetica", 9)
                y = height - 50
            c.drawString(50, y, line)
            y -= 13
        y -= 8
    c.save()
