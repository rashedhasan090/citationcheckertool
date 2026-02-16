#!/usr/bin/env python3
"""
Citation Checker - Command-line interface.
Usage:
  python cli.py                    # interactive: paste citations, then check
  python cli.py input.txt         # check citations from file
  python cli.py input.txt -o report.json  # export report
"""

import argparse
import sys
from pathlib import Path

# Allow running from repo root or from citation_checker/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from citation_checker import (
    CitationChecker,
    parse_citations,
    export_json,
    export_csv,
    export_pdf,
)


def main():
    parser = argparse.ArgumentParser(
        description="Citation Checker: validate DOI, URL, year, author; detect fakes; suggest fixes."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Input file with citations (BibTeX, APA, or one per line). Omit to paste from stdin.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Export report to file. Extension .json, .csv, or .pdf.",
    )
    parser.add_argument(
        "--no-doi-check",
        action="store_true",
        help="Skip online DOI validation (faster, no network).",
    )
    parser.add_argument(
        "--no-url-check",
        action="store_true",
        help="Skip URL accessibility check.",
    )
    args = parser.parse_args()

    if args.input:
        path = Path(args.input)
        if not path.exists():
            print(f"Error: file not found: {path}", file=sys.stderr)
            sys.exit(1)
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        print("Paste your citations below (BibTeX, APA, or one per line). End with Ctrl+D (Unix) or Ctrl+Z (Windows).")
        text = sys.stdin.read()

    citations, fmt = parse_citations(text)
    if not citations:
        print("No citations detected.", file=sys.stderr)
        sys.exit(1)
    print(f"Detected format: {fmt}. Parsed {len(citations)} citation(s).\n")

    checker = CitationChecker(
        check_doi_online=not args.no_doi_check,
        check_url_online=not args.no_url_check,
    )
    results = checker.check_many(citations)

    # Status summary
    status_counts = {}
    for r in results:
        status_counts[r.status] = status_counts.get(r.status, 0) + 1
    print("--- Status summary ---")
    for s, c in sorted(status_counts.items(), key=lambda x: -x[1]):
        print(f"  {s}: {c}")
    print()

    # Per-citation status
    print("--- Results ---")
    for r in results:
        icon = {"valid": "✓", "warning": "⚠", "invalid": "✗", "suspected_fake": "⚠ FAKE?"}.get(
            r.status, "?"
        )
        print(f"[{r.index}] {icon} {r.status}")
        if r.doi:
            print(f"    DOI: {r.doi} (resolved: {r.doi_resolved})")
        if r.year:
            print(f"    Year: {r.year}")
        if r.authors:
            print(f"    Authors: {', '.join(r.authors[:3])}{'…' if len(r.authors) > 3 else ''}")
        for issue in r.issues:
            print(f"    Issue: {issue}")
        for sug in r.suggestions:
            print(f"    Suggestion: {sug}")
        print()

    if args.output:
        out = Path(args.output)
        suffix = out.suffix.lower()
        try:
            if suffix == ".json":
                export_json(results, str(out))
            elif suffix == ".csv":
                export_csv(results, str(out))
            elif suffix == ".pdf":
                export_pdf(results, str(out))
            else:
                print(f"Unknown output format: {suffix}. Use .json, .csv, or .pdf.", file=sys.stderr)
                sys.exit(1)
            print(f"Report exported to {out}")
        except Exception as e:
            print(f"Export failed: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
