import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import Candidate, Citation, VerificationResult
from .scoring import claim_support_score, metadata_score, tokens
from .sources import ScholarlySources


class VerificationEngine:
    def __init__(self, timeout: int = 12, workers: int = 8, mailto: str | None = None):
        self.sources = ScholarlySources(timeout=timeout, mailto=mailto)
        self.workers = workers

    def _queries(self, citation: Citation) -> list[str]:
        q = []
        if citation.title:
            q.append(citation.title)
            words = tokens(citation.title)
            if len(words) > 8:
                q.append(" ".join(words[:8]))
            if len(words) > 4:
                q.append(" ".join(words[:4] + words[-2:]))
        if citation.authors and citation.year:
            q.append(f"{citation.authors[0]} {citation.year} {citation.title or ''}".strip())
        if not q:
            q = [citation.raw[:350]]
        seen = []
        for x in q:
            x = re.sub(r"\s+", " ", x).strip()
            if x and x not in seen:
                seen.append(x)
        return seen[:3]

    def verify(self, citation: Citation, deep: bool = False, find_alternatives: bool = True) -> VerificationResult:
        queries = self._queries(citation)
        calls = []
        calls.append(("crossref", lambda: self.sources.crossref(queries[0], citation.doi)))
        calls.append(("openalex", lambda: self.sources.openalex(queries[0], citation.doi)))
        if deep:
            for q in queries:
                calls.extend([
                    ("s2", lambda q=q: self.sources.semantic_scholar(q, citation.doi if q == queries[0] else None)),
                    ("pubmed", lambda q=q: self.sources.pubmed(q)),
                    ("arxiv", lambda q=q: self.sources.arxiv(q)),
                    ("openlibrary", lambda q=q: self.sources.openlibrary(q)),
                ])
            for q in queries[1:]:
                calls.extend([("crossref", lambda q=q: self.sources.crossref(q)), ("openalex", lambda q=q: self.sources.openalex(q))])

        evidence = []
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = [ex.submit(fn) for _, fn in calls]
            for fut in as_completed(futs):
                evidence.append(fut.result())

        scored = []
        source_scores = {}
        for ev in evidence:
            for cand in ev.candidates:
                score, parts = metadata_score(citation, cand)
                scored.append((score, cand, parts))
                source_scores[cand.source] = max(score, source_scores.get(cand.source, 0.0))
        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best, parts = scored[0] if scored else (0.0, None, {})

        corroborating = set()
        if best:
            for score, cand, _ in scored:
                same_doi = bool(best.doi and cand.doi and best.doi.lower() == cand.doi.lower())
                same_title = metadata_score(Citation(raw="", title=best.title, authors=best.authors, year=best.year, doi=best.doi), cand)[0] >= 0.82
                if same_doi or same_title:
                    corroborating.add(cand.source)
        confidence = int(round(min(1.0, best_score + min(0.08, 0.025 * max(0, len(corroborating) - 1))) * 100))

        notices = []
        if not citation.title:
            notices.append("Could not confidently parse a title from the reference.")
        if best:
            if citation.year and best.year and citation.year != best.year:
                notices.append(f"Year mismatch: cited {citation.year}, matched record {best.year}.")
            if citation.doi and best.doi and citation.doi.lower() != best.doi.lower():
                notices.append("DOI mismatch between citation and strongest matched record.")
            if parts.get("authors", 1) < 0.5 and citation.authors:
                notices.append("Author list differs substantially from the strongest matched record.")
            if best.is_retracted:
                notices.append("Matched OpenAlex record is flagged as retracted.")

        if best_score >= 0.82 or (citation.doi and best and best.doi and citation.doi.lower() == best.doi.lower() and best_score >= 0.70):
            assessment = "authentic_with_notice" if notices else "authentic"
        elif best_score >= 0.58:
            assessment = "unsure"
        else:
            assessment = "not_found" if best_score < 0.40 else "unsure"

        support_score, support_note = claim_support_score(citation.context, best) if best else (None, None)
        alternatives = []
        if find_alternatives and assessment in {"not_found", "unsure"}:
            seen = set()
            for score, cand, _ in scored:
                key = (cand.doi or cand.title).lower()
                if key in seen:
                    continue
                seen.add(key)
                if cand is not best and score >= 0.35:
                    alternatives.append(cand)
                if len(alternatives) >= 5:
                    break

        return VerificationResult(citation=citation, assessment=assessment, confidence=confidence, matched=best,
                                  notices=notices, evidence_sources=sorted({e.source for e in evidence if e.candidates}),
                                  source_scores={k: round(v, 3) for k, v in source_scores.items()}, support_score=support_score,
                                  support_note=support_note, alternatives=alternatives, deep_verified=deep)

    def verify_many(self, citations: list[Citation], deep: bool = False) -> list[VerificationResult]:
        out = [None] * len(citations)
        with ThreadPoolExecutor(max_workers=min(self.workers, max(1, len(citations)))) as ex:
            futs = {ex.submit(self.verify, c, deep): i for i, c in enumerate(citations)}
            for fut in as_completed(futs):
                out[futs[fut]] = fut.result()
        return out

    def find(self, query: str, limit: int = 10) -> list[Candidate]:
        evs = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [ex.submit(self.sources.openalex, query, None, limit), ex.submit(self.sources.crossref, query, None, limit),
                    ex.submit(self.sources.semantic_scholar, query, None, limit), ex.submit(self.sources.pubmed, query, limit)]
            for f in as_completed(futs):
                evs.append(f.result())
        candidates = []
        seen = set()
        for e in evs:
            for c in e.candidates:
                key = c.doi or re.sub(r"\W+", "", c.title.lower())
                if key and key not in seen:
                    seen.add(key)
                    candidates.append(c)
        return candidates[:limit]
