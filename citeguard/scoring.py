import re
from collections import Counter
from rapidfuzz.fuzz import ratio

from .models import Candidate, Citation

STOP = {"a","an","the","and","or","of","to","in","for","on","with","by","from","at","as","is","are","be","using","via"}


def norm(s: str | None) -> str:
    if not s:
        return ""
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


def tokens(s: str | None) -> list[str]:
    return [x for x in norm(s).split() if len(x) > 2 and x not in STOP]


def title_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return ratio(norm(a), norm(b)) / 100.0


def author_similarity(cited: list[str], actual: list[str]) -> float:
    if not cited or not actual:
        return 0.0
    c = set(tokens(" ".join(cited)))
    a = set(tokens(" ".join(actual)))
    return len(c & a) / max(1, min(len(c), len(a)))


def venue_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return ratio(norm(a), norm(b)) / 100.0


def metadata_score(citation: Citation, candidate: Candidate) -> tuple[float, dict[str, float]]:
    t = title_similarity(citation.title, candidate.title)
    au = author_similarity(citation.authors, candidate.authors)
    y = 1.0 if citation.year and candidate.year and citation.year == candidate.year else (0.5 if not citation.year or not candidate.year else 0.0)
    v = venue_similarity(citation.venue, candidate.venue) if citation.venue else 0.5
    d = 1.0 if citation.doi and candidate.doi and citation.doi.lower() == candidate.doi.lower() else 0.0
    if d == 1.0:
        score = 0.50*d + 0.30*t + 0.10*au + 0.07*y + 0.03*v
    else:
        score = 0.55*t + 0.25*au + 0.15*y + 0.05*v
    return score, {"title": t, "authors": au, "year": y, "venue": v, "doi": d}


def claim_support_score(claim: str | None, candidate: Candidate) -> tuple[int | None, str | None]:
    if not claim:
        return None, None
    evidence = " ".join(x for x in [candidate.title, candidate.abstract or ""] if x)
    if not evidence:
        return None, "No abstract/summary was available for claim-support analysis."
    q = Counter(tokens(claim))
    e = Counter(tokens(evidence))
    if not q:
        return None, None
    overlap = sum(min(q[k], e[k]) for k in q) / max(1, sum(q.values()))
    phrase = ratio(norm(claim), norm(evidence[:1200])) / 100.0
    score = int(round(100 * min(1.0, 0.8 * overlap + 0.2 * phrase)))
    if score >= 60:
        note = "Strong lexical support signal; inspect the source before relying on it for the claim."
    elif score >= 35:
        note = "Partial support signal; the citation may be topically related but manual reading is recommended."
    else:
        note = "Weak support signal; the matched publication may not substantiate the supplied claim."
    return score, note
