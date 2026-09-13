import csv
import json
from pathlib import Path

from .models import VerificationResult


def flatten(r: VerificationResult) -> dict:
    return {
        "index": r.citation.index,
        "assessment": r.assessment,
        "confidence": r.confidence,
        "integrity_score": r.integrity_score,
        "risk_level": r.risk_level,
        "metadata_consistency": r.metadata_consistency,
        "failure_modes": ", ".join(r.failure_modes),
        "corroborating_sources": ", ".join(r.corroborating_sources),
        "cited_title": r.citation.title or "",
        "cited_doi": r.citation.doi or "",
        "matched_title": r.matched.title if r.matched else "",
        "matched_doi": r.matched.doi if r.matched else "",
        "matched_year": r.matched.year if r.matched else "",
        "matched_source": r.matched.source if r.matched else "",
        "retracted": bool(r.matched and r.matched.is_retracted),
        "post_publication_updates": " | ".join(r.matched.integrity_updates) if r.matched else "",
        "citation_count": r.matched.citation_count if r.matched else "",
        "open_access": r.matched.is_open_access if r.matched else "",
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
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["index"])
        writer.writeheader()
        writer.writerows(rows)


def export_pdf(results, path):
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(str(path), pagesize=letter)
    _, height = letter
    y = height - 50
    c.setTitle("CiteGuard Research Integrity Report")
    c.setFont("Helvetica-Bold", 17)
    c.drawString(50, y, "CiteGuard Research Integrity Report")
    y -= 20
    c.setFont("Helvetica", 8)
    c.drawString(50, y, "Evidence-first citation verification. Scores are triage signals and require human review.")
    y -= 28
    for r in results:
        lines = [
            f"[{r.citation.index}] {r.assessment.replace('_', ' ').upper()} | confidence {r.confidence}% | integrity {r.integrity_score}/100 | risk {r.risk_level}",
            f"Citation: {r.citation.raw[:125]}",
            f"Best match: {(r.matched.title if r.matched else 'None')[:115]}",
            f"Corroboration: {', '.join(r.corroborating_sources) or 'none'}",
        ]
        if r.failure_modes:
            lines.append("Integrity signals: " + ", ".join(r.failure_modes)[:115])
        if r.notices:
            lines.append("Notices: " + "; ".join(r.notices)[:115])
        if r.matched and r.matched.doi:
            lines.append("DOI: " + r.matched.doi[:110])
        for line in lines:
            if y < 70:
                c.showPage()
                c.setFont("Helvetica", 8)
                y = height - 50
            c.drawString(50, y, line)
            y -= 13
        y -= 9
    c.save()
