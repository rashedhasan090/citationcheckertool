# CiteGuard 🛡️

**Professional citation verification and research-integrity intelligence — CLI + SaaS web application.**

CiteGuard verifies whether references resolve to real scholarly records, checks whether cited metadata agrees with authoritative indexes, and adds a research-integrity layer for mismatched identifiers, possible composite citations, post-publication updates, retractions, and evidence provenance.

> CiteGuard is an independent product. It is not affiliated with CiteTrue, GPTZero, Scite, or other commercial research-integrity platforms and does not copy their proprietary code, data, models, branding, or interfaces.

## CiteGuard 3.0

- Crossref, OpenAlex, Semantic Scholar, PubMed, arXiv, and Open Library evidence
- Fast Verify and wider Deep Verify
- Research Integrity Score with low / moderate / high / critical triage levels
- Identifier, title, author, year, and venue mismatch taxonomy
- Citation Fingerprint analysis for possible composite/amalgamated references
- Retraction, correction, and expression-of-concern signals where scholarly metadata exposes them
- Citation counts and open-access metadata where available
- Optional claim-to-source alignment screening
- Citation Finder / evidence discovery
- Batch input: plain references, BibTeX, RIS, PDF, DOCX, TXT/Markdown
- CSV, JSON, and PDF reports
- User accounts, credit ledger, tier entitlements, history, and superadmin console
- Salted PBKDF2 password hashing; plaintext credentials are never committed to the repository

## Plans

| Plan | Price | Credits | Key capabilities |
|---|---:|---:|---|
| Free | $0 | 100 welcome credits | Fast Verify, Citation Finder, CSV |
| Researcher | $9/mo | 1,500/mo | Deep Verify, Integrity Score, post-publication intelligence, JSON/PDF |
| Pro | $19/mo | 5,000/mo | Batch audit, claim alignment, Citation Fingerprint, expanded discovery |
| Lab | $49/mo | 20,000/mo | High-volume audit, team-ready reporting, advanced integrity analytics |

The configured superadmin receives unlimited access to all capabilities.

## Live application

https://citeguard-2uw9.onrender.com

## Local web app

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## CLI

```bash
pip install -e .
citeguard verify references.bib
citeguard verify paper.pdf --deep
citeguard find "hallucinated citations in scientific writing"
```

## Production configuration

Never commit credentials, reset tokens, database URLs, or API secrets. Configure them in Render environment variables or another secret manager.

CiteGuard supports PostgreSQL through SQLAlchemy and uses SQLite only as a development fallback. Attach a managed PostgreSQL database before onboarding paid users because an ephemeral hosting filesystem can be reset during redeploys.

Tier entitlements are implemented. Stripe payment links are read from environment variables, so billing URLs and secrets do not need to enter Git history. Subscription/webhook synchronization should be enabled before accepting production recurring payments.

## Verification philosophy

CiteGuard does not treat an LLM as the authority on whether a publication exists. It retrieves evidence from scholarly indexes, normalizes records, scores DOI/title/author/year/venue consistency, checks cross-source corroboration, and reports uncertainty explicitly.

A `not_found` result is not proof of fabrication. Research-integrity scores are triage signals, not accusations of misconduct.

## License

MIT © 2026 Md Rashedul Hasan
