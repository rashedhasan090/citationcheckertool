from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from .engine import VerificationEngine
from .exporters import export_csv, export_json, export_pdf
from .parsers import extract_references_section, extract_text_from_file, parse_citations

app = typer.Typer(help="CiteGuard — free deep citation verification")
console = Console()


def _read(source: Optional[Path], text: Optional[str]) -> str:
    if text:
        return text
    if source:
        return extract_text_from_file(source)
    console.print("Paste references, then press Ctrl-D (Ctrl-Z on Windows):")
    import sys
    return sys.stdin.read()


@app.command()
def verify(source: Optional[Path] = typer.Argument(None, help="TXT/BIB/RIS/PDF/DOCX file"),
           text: Optional[str] = typer.Option(None, "--text", "-t"), deep: bool = typer.Option(False, "--deep", "-d"),
           context: Optional[str] = typer.Option(None, "--context", help="Claim/context to test against a single citation"),
           output: Optional[Path] = typer.Option(None, "--output", "-o"), timeout: int = 12):
    """Verify one citation or a batch of references."""
    raw = extract_references_section(_read(source, text))
    citations = parse_citations(raw)
    if context and len(citations) == 1:
        citations[0].context = context
    engine = VerificationEngine(timeout=timeout)
    with console.status(f"Verifying {len(citations)} citation(s){' deeply' if deep else ''}..."):
        results = engine.verify_many(citations, deep=deep)
    table = Table(title="CiteGuard results")
    for col in ["#", "Assessment", "Conf.", "Matched title", "Sources", "Notices"]:
        table.add_column(col)
    for r in results:
        table.add_row(str(r.citation.index), r.assessment, str(r.confidence), (r.matched.title[:55] if r.matched else "—"),
                      ", ".join(r.evidence_sources), "; ".join(r.notices)[:60])
    console.print(table)
    if output:
        ext = output.suffix.lower()
        if ext == ".json":
            export_json(results, output)
        elif ext == ".csv":
            export_csv(results, output)
        elif ext == ".pdf":
            export_pdf(results, output)
        else:
            raise typer.BadParameter("Output must end in .json, .csv, or .pdf")
        console.print(f"Saved {output}")


@app.command("find")
def find_citations(query: str, limit: int = 10):
    """Find real papers for a topic, claim, or partial citation."""
    rows = VerificationEngine().find(query, limit)
    t = Table(title="Citation Finder")
    for c in ["#", "Title", "Year", "Source", "DOI"]:
        t.add_column(c)
    for i, x in enumerate(rows, 1):
        t.add_row(str(i), x.title[:70], str(x.year or ""), x.source, x.doi or "")
    console.print(t)


@app.command()
def web(port: int = 8501):
    """Launch the Streamlit GUI locally."""
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[1]
    raise typer.Exit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(root / "app.py"), "--server.port", str(port)]))


if __name__ == "__main__":
    app()
