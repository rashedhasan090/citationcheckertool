# CiteGuard 🛡️

**Free, open-source deep citation verification and validation — CLI + web GUI.**

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2Frashedhasan090%2Fcitationcheckertool)

CiteGuard is an evidence-first alternative for researchers who want to check whether references resolve to real scholarly records and whether the cited metadata agrees with authoritative indexes. It is not affiliated with CiteTrue and does not copy CiteTrue's proprietary code, branding, or interface.

## What it checks

- Multi-source existence verification: **Crossref, OpenAlex, Semantic Scholar, PubMed, arXiv, Open Library**
- **Fast Verify**: Crossref + OpenAlex
- **Deep Verify**: wider databases + multiple search-query variants + cross-source consensus
- DOI, title, author, year, and venue agreement
- Retraction signal when OpenAlex marks a work as retracted
- Confidence score with transparent mismatch notices
- Optional **claim-support signal** using the matched title/abstract
- **Citation Finder** for real papers from a topic, claim, or partial citation
- Suggested nearby/replacement records when a citation cannot be confidently resolved
- Batch input: plain references, numbered lists, **BibTeX, RIS, PDF, DOCX, TXT/Markdown**
- Export: **CSV, JSON, PDF**
- Parallel verification for large bibliographies
- No account, credits, or subscription

> Important: `not_found` is not proof that a reference is fabricated. Bibliographic coverage is incomplete; manually review uncertain or missing records.

## Install as a CLI

```bash
git clone https://github.com/rashedhasan090/citationcheckertool.git
cd citationcheckertool
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Then:

```bash
citeguard verify references.bib
citeguard verify paper.pdf --deep
citeguard verify --text "Vaswani et al. (2017). Attention Is All You Need." --deep --context "Transformers replace recurrence with self-attention."
citeguard verify references.txt --deep -o report.csv
citeguard verify references.txt --deep -o report.json
citeguard verify references.txt --deep -o report.pdf
citeguard find "LLM hallucinated citations in scientific writing"
citeguard web
```

## Web GUI

```bash
pip install -r requirements.txt
streamlit run app.py
```

The GUI includes **Verify citations**, **Citation Finder**, deep/fast modes, per-citation evidence, retraction warnings, alternatives, and report downloads.

## Free deployment

### Render

Use the **Deploy to Render** button at the top of this README. The repo includes a root-level `render.yaml` Blueprint configured for a free Python web service, Streamlit health checks, and automatic deployment only after GitHub CI passes.

Build command: `pip install -r requirements.txt`

Start command: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT`

### Streamlit Community Cloud

1. Sign in at Streamlit Community Cloud with GitHub.
2. Create a new app from `rashedhasan090/citationcheckertool`.
3. Branch: `main`; main file: `app.py`.
4. Deploy. No secrets are required for the public scholarly APIs used by default.

## Verification design

CiteGuard does not use an LLM as an oracle for publication existence. It searches bibliographic indexes, normalizes returned records, and computes a weighted metadata score. DOI equality is strongest evidence; otherwise title, author, year, and venue agreement are combined. Deep mode broadens sources and search strategies and rewards cross-source corroboration.

The optional claim-support score is explicitly a **screening signal**, not a factual entailment guarantee. It compares the supplied claim with the title/abstract text available from the matched record and should be followed by reading the publication.

## Privacy

Citations are sent only to the scholarly APIs required for lookup. Uploaded files are parsed locally by the running app. CiteGuard does not require an account and does not contain telemetry.

## Responsible-use note

Use CiteGuard to audit references, review manuscripts, and detect citation problems. Do not use it to fabricate references or to misrepresent unverified sources as genuine.

## License

MIT © 2026 Md Rashedul Hasan
