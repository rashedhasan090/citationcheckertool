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
        queries = []
        if citation.title:
            queries.append(citation.title)
            words = tokens(citation.title)
            if len(words) > 8:
                queries.append(" ".join(words[:8]))
            if len(words) > 4:
                queries.append(" ".join(words[:4] + words[-2:]))
        if citation.authors and citation.year:
            queries.append(f"{citation.authors[0]} {citation.year} {citation.title or ''}".strip())
        if not queries:
            queries = [citation.raw[:350]]
        seen = []
        for q in queries:
            q = re.sub(r"\s+", " ", q).strip()
            if q and q not in seen:
                seen.append(q)
        return seen[:3]

    @staticmethod
    def _integrity_analysis(citation, best, best_score, parts, scored, assessment, corroborating):
        failures = []
        if assessment == "not_found":
            failures.append("unresolved_reference")
        if best:
            if citation.doi and best.doi and citation.doi.lower() != best.doi.lower():
                failures.append("identifier_mismatch")
            if citation.title and parts.get("title", 1) < 0.72:
                failures.append("title_mismatch")
            if citation.authors and parts.get("authors", 1) < 0.50:
                failures.append("author_mismatch")
            if citation.year and best.year and citation.year != best.year:
                failures.append("year_mismatch")
            if citation.venue and best.venue and parts.get("venue", 1) < 0.45:
                failures.append("venue_mismatch")
            if best.is_retracted:
                failures.append("retracted_source")
            for update in best.integrity_updates:
                low = update.lower()
                if "expression" in low and "concern" in low:
                    failures.append("expression_of_concern")
                elif "correct" in low:
                    failures.append("corrected_source")

        title_best = author_best = doi_best = None
        for _, cand, candidate_parts in scored:
            if title_best is None or candidate_parts.get("title", 0) > title_best[0]:
                title_best = (candidate_parts.get("title", 0), cand)
            if author_best is None or candidate_parts.get("authors", 0) > author_best[0]:
                author_best = (candidate_parts.get("authors", 0), cand)
            if citation.doi and cand.doi and citation.doi.lower() == cand.doi.lower():
                doi_best = cand

        amalgamation = False
        if title_best and title_best[0] >= 0.86:
            title_cand = title_best[1]
            if author_best and author_best[0] >= 0.72 and author_best[1].title != title_cand.title:
                amalgamation = True
            if doi_best and doi_best.title != title_cand.title:
                amalgamation = True
        if amalgamation:
            failures.append("possible_composite_citation")

        score = 22 if assessment == "not_found" else 58 if assessment == "unsure" else 82 if assessment == "authentic_with_notice" else 94
        score += min(6, max(0, len(corroborating) - 1) * 2)
        penalties = {
            "identifier_mismatch": 22, "title_mismatch": 18, "author_mismatch": 14,
            "year_mismatch": 8, "venue_mismatch": 6, "retracted_source": 45,
            "expression_of_concern": 25, "corrected_source": 5, "possible_composite_citation": 24,
        }
        for failure in set(failures):
            score -= penalties.get(failure, 0)
        score = max(0, min(100, score))
        risk = "low" if score >= 85 else "moderate" if score >= 65 else "high" if score >= 40 else "critical"
        metadata_consistency = int(round(min(1.0, best_score) * 100)) if best else 0
        return score, risk, sorted(set(failures)), metadata_consistency, amalgamation

    def verify(self, citation: Citation, deep: bool = False, find_alternatives: bool = True) -> VerificationResult:
        queries = self._queries(citation)
        calls = [
            lambda: self.sources.crossref(queries[0], citation.doi),
            lambda: self.sources.openalex(queries[0], citation.doi),
        ]
        if deep:
            for q in queries:
                calls.extend([
                    lambda q=q: self.sources.semantic_scholar(q, citation.doi if q == queries[0] else None),
                    lambda q=q: self.sources.pubmed(q),
                    lambda q=q: self.sources.arxiv(q),
                    lambda q=q: self.sources.openlibrary(q),
                ])
            for q in queries[1:]:
                calls.extend([lambda q=q: self.sources.crossref(q), lambda q=q: self.sources.openalex(q)])

        evidence = []
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = [executor.submit(fn) for fn in calls]
            for future in as_completed(futures):
                try:
                    evidence.append(future.result())
                except Exception:
                    continue

        scored, source_scores = [], {}
        for ev in evidence:
            for candidate in ev.candidates:
                score, parts = metadata_score(citation, candidate)
                scored.append((score, candidate, parts))
                source_scores[candidate.source] = max(score, source_scores.get(candidate.source, 0.0))
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best, parts = scored[0] if scored else (0.0, None, {})

        corroborating = set()
        if best:
            fingerprint = Citation(raw="", title=best.title, authors=best.authors, year=best.year, doi=best.doi)
            for _, candidate, _ in scored:
                same_doi = bool(best.doi and candidate.doi and best.doi.lower() == candidate.doi.lower())
                same_title = metadata_score(fingerprint, candidate)[0] >= 0.82
                if same_doi or same_title:
                    corroborating.add(candidate.source)
        confidence = int(round(min(1.0, best_score + min(0.08, 0.025 * max(0, len(corroborating) - 1))) * 100))

        notices = []
        if not citation.title:
            notices.append("Could not confidently parse a title from the reference.")
        if best:
            if citation.year and best.year and citation.year != best.year:
                notices.append(f"Year mismatch: cited {citation.year}, matched record {best.year}.")
            if citation.doi and best.doi and citation.doi.lower() != best.doi.lower():
                notices.append("DOI mismatch between citation and strongest matched record.")
            if citation.authors and parts.get("authors", 1) < 0.5:
                notices.append("Author list differs substantially from the strongest matched record.")
            if best.is_retracted:
                notices.append("Retraction signal detected in scholarly metadata.")
            if best.integrity_updates:
                notices.append("Post-publication updates: " + ", ".join(best.integrity_updates[:4]))

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
            for score, candidate, _ in scored:
                key = (candidate.doi or candidate.title).lower()
                if key in seen:
                    continue
                seen.add(key)
                if candidate is not best and score >= 0.35:
                    alternatives.append(candidate)
                if len(alternatives) >= 5:
                    break

        integrity_score, risk_level, failure_modes, metadata_consistency, amalgamation = self._integrity_analysis(
            citation, best, best_score, parts, scored, assessment, corroborating
        )
        return VerificationResult(
            citation=citation, assessment=assessment, confidence=confidence, matched=best,
            notices=notices, evidence_sources=sorted({e.source for e in evidence if e.candidates}),
            source_scores={k: round(v, 3) for k, v in source_scores.items()}, support_score=support_score,
            support_note=support_note, alternatives=alternatives, deep_verified=deep,
            integrity_score=integrity_score, risk_level=risk_level, failure_modes=failure_modes,
            corroborating_sources=sorted(corroborating), metadata_consistency=metadata_consistency,
            amalgamation_risk=amalgamation,
        )

    def verify_many(self, citations: list[Citation], deep: bool = False) -> list[VerificationResult]:
        output = [None] * len(citations)
        with ThreadPoolExecutor(max_workers=min(self.workers, max(1, len(citations)))) as executor:
            futures = {executor.submit(self.verify, citation, deep): i for i, citation in enumerate(citations)}
            for future in as_completed(futures):
                output[futures[future]] = future.result()
        return output

    def find(self, query: str, limit: int = 10) -> list[Candidate]:
        evidence = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(self.sources.openalex, query, None, limit),
                executor.submit(self.sources.crossref, query, None, limit),
                executor.submit(self.sources.semantic_scholar, query, None, limit),
                executor.submit(self.sources.pubmed, query, limit),
            ]
            for future in as_completed(futures):
                try:
                    evidence.append(future.result())
                except Exception:
                    continue
        candidates, seen = [], set()
        for ev in evidence:
            for candidate in ev.candidates:
                key = candidate.doi or re.sub(r"\W+", "", candidate.title.lower())
                if key and key not in seen:
                    seen.add(key)
                    candidates.append(candidate)
        candidates.sort(key=lambda candidate: candidate.citation_count or 0, reverse=True)
        return candidates[:limit]
