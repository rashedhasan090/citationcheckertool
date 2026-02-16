"""
Citation Checker - Web GUI (Streamlit). Run: streamlit run app.py
Deploy to Streamlit Community Cloud for free hosting.
"""

import streamlit as st
from citation_checker import (
    CitationChecker,
    parse_citations,
    export_json,
    export_csv,
    export_pdf,
)

st.set_page_config(
    page_title="Citation Checker",
    page_icon="📚",
    layout="wide",
)

st.title("📚 Citation Checker")
st.caption("Paste citations from your paper (BibTeX, APA, or unformatted). We check DOI, URL, year, author and flag suspected fakes.")

with st.sidebar:
    st.subheader("Options")
    check_doi = st.checkbox("Validate DOI online (CrossRef)", value=True)
    check_url = st.checkbox("Check URL accessibility", value=True)
    st.divider()
    st.caption("Export report below after running a check.")

input_text = st.text_area(
    "Paste citations here",
    height=220,
    placeholder="Paste BibTeX (@article{...}), APA (Author, A. (year). Title...), or one citation per line.",
    help="Supports BibTeX, APA, and unformatted (line- or paragraph-separated) citations.",
)

if st.button("Check citations", type="primary"):
    if not input_text or not input_text.strip():
        st.warning("Please paste some citations first.")
    else:
        citations, fmt = parse_citations(input_text)
        if not citations:
            st.error("No citations could be parsed. Try BibTeX, APA, or one full citation per line.")
        else:
            st.success(f"Detected format: **{fmt}**. Parsed **{len(citations)}** citation(s).")
            checker = CitationChecker(
                check_doi_online=check_doi,
                check_url_online=check_url,
            )
            with st.spinner("Checking DOI, URL, year, author…"):
                results = checker.check_many(citations)

            # Store in session for export
            st.session_state["last_results"] = results
            st.session_state["last_format"] = fmt

            # Summary
            valid = sum(1 for r in results if r.status == "valid")
            warning = sum(1 for r in results if r.status == "warning")
            fake = sum(1 for r in results if r.status == "suspected_fake")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total", len(results))
            col2.metric("Valid", valid)
            col3.metric("Warning", warning)
            col4.metric("Suspected fake", fake)

            # Per-citation status
            st.subheader("Results")
            for r in results:
                status_emoji = {"valid": "✅", "warning": "⚠️", "invalid": "❌", "suspected_fake": "🚨"}.get(r.status, "❓")
                with st.expander(f"{status_emoji} Citation #{r.index} — {r.status}", expanded=(r.status != "valid")):
                    st.write("**Raw (preview):**", r.raw[:400] + ("…" if len(r.raw) > 400 else ""))
                    if r.doi:
                        st.write("**DOI:**", r.doi, "— Resolved:" if r.doi_resolved is True else "— Not resolved" if r.doi_resolved is False else "— Not checked")
                    if r.year:
                        st.write("**Year:**", r.year)
                    if r.authors:
                        st.write("**Authors:**", ", ".join(r.authors))
                    if r.issues:
                        st.write("**Issues:**")
                        for i in r.issues:
                            st.write("-", i)
                    if r.suggestions:
                        st.write("**Suggestions:**")
                        for s in r.suggestions:
                            st.write("-", s)

            # Export
            st.divider()
            st.subheader("Export report")
            c1, c2, c3 = st.columns(3)
            with c1:
                if st.download_button(
                    "Download JSON",
                    data=__results_to_json_string(results),
                    file_name="citation_report.json",
                    mime="application/json",
                ):
                    st.caption("JSON downloaded.")
            with c2:
                buf = __results_to_csv_string(results)
                if st.download_button(
                    "Download CSV",
                    data=buf,
                    file_name="citation_report.csv",
                    mime="text/csv",
                ):
                    st.caption("CSV downloaded.")
            with c3:
                try:
                    import tempfile
                    import os
                    from pathlib import Path
                    fd, path = tempfile.mkstemp(suffix=".pdf")
                    try:
                        os.close(fd)
                        export_pdf(results, path)
                        pdf_bytes = Path(path).read_bytes()
                    finally:
                        try:
                            os.unlink(path)
                        except Exception:
                            pass
                    st.download_button(
                        "Download PDF",
                        data=pdf_bytes,
                        file_name="citation_report.pdf",
                        mime="application/pdf",
                    )
                except Exception as e:
                    st.caption("PDF export requires reportlab. Install: pip install reportlab")

else:
    if "last_results" in st.session_state:
        st.info("Run a new check above, or use the export buttons that appeared after the last check.")

# Helpers for download buttons (Streamlit needs string/bytes)
def __results_to_json_string(results):
    import json
    from datetime import datetime
    data = {
        "generated": datetime.utcnow().isoformat() + "Z",
        "total": len(results),
        "citations": [
            {
                "index": r.index,
                "status": r.status,
                "issues": r.issues,
                "suggestions": r.suggestions,
                "doi": r.doi,
                "year": r.year,
                "authors": r.authors,
            }
            for r in results
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False)


def __results_to_csv_string(results):
    import csv
    import io
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(["Index", "Status", "DOI", "Year", "Issues", "Suggestions"])
    for r in results:
        w.writerow([
            r.index,
            r.status,
            r.doi or "",
            r.year or "",
            " | ".join(r.issues),
            " | ".join(r.suggestions),
        ])
    return out.getvalue()
