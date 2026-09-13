import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from citeguard.engine import VerificationEngine
from citeguard.exporters import flatten
from citeguard.parsers import extract_references_section, extract_text_from_file, parse_citations

st.set_page_config(page_title="CiteGuard", page_icon="🛡️", layout="wide")
st.title("🛡️ CiteGuard")
st.caption("Free, open-source deep citation verification. Multi-source evidence, no credits, no paywall.")

with st.sidebar:
    st.header("Verification")
    deep = st.toggle("Deep Verify", value=True, help="Searches more scholarly sources and query variants.")
    timeout = st.slider("Network timeout", 5, 30, 12)
    st.markdown("**Fast:** Crossref + OpenAlex  \n**Deep:** + Semantic Scholar, PubMed, arXiv, Open Library")
    st.info("A 'not found' result is not proof of fabrication. Coverage varies by discipline, language, age, and publication type.")

tab_verify, tab_find, tab_about = st.tabs(["Verify citations", "Citation Finder", "How it works"])

with tab_verify:
    uploaded = st.file_uploader("Upload a paper/reference file", type=["txt", "bib", "ris", "pdf", "docx", "md"])
    pasted = st.text_area("Or paste references", height=220, placeholder="Paste numbered references, APA, BibTeX, RIS, or plain citations...")
    claim = st.text_area("Optional claim/context (best for verifying one citation)", height=80)
    if st.button("Verify", type="primary"):
        text = pasted
        if uploaded:
            suffix = Path(uploaded.name).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(uploaded.getvalue())
                path = tmp.name
            try:
                text = extract_text_from_file(path)
            finally:
                os.unlink(path)
        text = extract_references_section(text or "")
        citations = parse_citations(text)
        if claim and len(citations) == 1:
            citations[0].context = claim
        if not citations:
            st.error("No citations detected.")
        else:
            eng = VerificationEngine(timeout=timeout)
            bar = st.progress(0, text="Verifying...")
            results = []
            for i, c in enumerate(citations, 1):
                results.append(eng.verify(c, deep=deep))
                bar.progress(i / len(citations), text=f"Verified {i}/{len(citations)}")
            st.session_state["results"] = results
            bar.empty()

    results = st.session_state.get("results", [])
    if results:
        rows = [flatten(r) for r in results]
        a = sum(r.assessment.startswith("authentic") for r in results)
        u = sum(r.assessment == "unsure" for r in results)
        n = sum(r.assessment == "not_found" for r in results)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total", len(results))
        c2.metric("Authentic", a)
        c3.metric("Unsure", u)
        c4.metric("Not found", n)
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        for r in results:
            with st.expander(f"[{r.citation.index}] {r.assessment.replace('_', ' ').title()} — {r.confidence}%"):
                st.write(r.citation.raw)
                if r.matched:
                    st.markdown(f"**Best match:** {r.matched.title}  \n**Source:** {r.matched.source}  \n**DOI:** {r.matched.doi or '—'}  \n**Year:** {r.matched.year or '—'}")
                    if r.matched.is_retracted:
                        st.error("Retraction flag detected in OpenAlex metadata.")
                if r.notices:
                    st.warning("\n\n".join(r.notices))
                if r.support_score is not None:
                    st.metric("Claim-support signal", f"{r.support_score}%")
                    st.caption(r.support_note)
                if r.alternatives:
                    st.markdown("**Possible alternatives / nearby real records**")
                    for alt in r.alternatives[:5]:
                        st.write(f"- {alt.title} ({alt.year or 'n.d.'}) — {alt.source} — {alt.doi or alt.url or ''}")
        csv_bytes = pd.DataFrame(rows).to_csv(index=False).encode()
        json_bytes = json.dumps([r.to_dict() for r in results], indent=2).encode()
        c1, c2 = st.columns(2)
        c1.download_button("Download CSV", csv_bytes, "citeguard-report.csv", "text/csv")
        c2.download_button("Download JSON", json_bytes, "citeguard-report.json", "application/json")

with tab_find:
    q = st.text_input("Topic, claim, title fragment, DOI, or keywords")
    limit = st.slider("Results", 3, 20, 10, key="finder_limit")
    if st.button("Find real citations") and q:
        with st.spinner("Searching scholarly indexes..."):
            found = VerificationEngine(timeout=timeout).find(q, limit)
        for i, c in enumerate(found, 1):
            st.markdown(f"**{i}. {c.title}**  \n{', '.join(c.authors[:4])} · {c.year or 'n.d.'} · {c.source}  \n{c.doi or c.url or ''}")
            st.divider()

with tab_about:
    st.markdown("""
### Evidence-first verification
CiteGuard parses each reference, searches multiple scholarly indexes, normalizes candidate records, scores title/author/year/venue/DOI agreement, and reports the best-supported match plus mismatches.

### Deep Verify
Deep mode fans out several query variants across Crossref, OpenAlex, Semantic Scholar, PubMed, arXiv, and Open Library, then combines evidence. It never asks an LLM to simply *guess* whether a publication exists.

### Limits
No bibliographic index is complete. Books, theses, non-English work, very new papers, workshops, standards, and grey literature can be missed. Treat `unsure` and `not_found` as prompts for manual review, not accusations of misconduct.
""")
