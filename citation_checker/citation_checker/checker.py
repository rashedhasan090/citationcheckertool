"""
Core citation checker: DOI, URL, year, author validation and fake citation detection.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger(__name__)

CROSSREF_API = "https://api.crossref.org/works"
USER_AGENT = "CitationChecker/1.0 (mailto:user@example.com)"


@dataclass
class CitationResult:
    """Result of checking a single citation."""

    raw: str
    index: int
    status: str  # "valid", "warning", "invalid", "suspected_fake"
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    doi: Optional[str] = None
    url: Optional[str] = None
    year: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    title: Optional[str] = None
    doi_resolved: bool = False
    url_accessible: bool = False


def extract_doi(text: str) -> Optional[str]:
    """Extract DOI from text. Handles doi:10.xxx and https://doi.org/10.xxx."""
    text = text.strip()
    # doi:10.xxxx/yyyy
    m = re.search(r"(?:doi\s*[:\s]*)?(10\.\d{4,}/[^\s\]\)\}\"\']+)", text, re.I)
    if m:
        return m.group(1).rstrip(".,;")
    # https://doi.org/10.xxxx/yyyy
    m = re.search(r"https?://(?:dx\.)?doi\.org/(10\.\d{4,}/[^\s\]\)\}\"\']+)", text, re.I)
    if m:
        return m.group(1).rstrip(".,;")
    return None


def extract_year(text: str) -> Optional[str]:
    """Extract 4-digit year from text."""
    matches = re.findall(r"\b(19\d{2}|20\d{2})\b", text)
    return matches[-1] if matches else None


def extract_urls(text: str) -> list[str]:
    """Extract HTTP/HTTPS URLs from text."""
    url_pattern = r"https?://[^\s\]\)\}\"\']+"
    return re.findall(url_pattern, text)


def validate_doi(doi: str) -> tuple[bool, Optional[dict]]:
    """
    Validate DOI via CrossRef API. Returns (found, metadata).
    No API key required for public CrossRef.
    """
    if not doi or not doi.startswith("10."):
        return False, None
    doi_clean = doi.strip().rstrip(".,;")
    try:
        r = requests.get(
            f"{CROSSREF_API}/{doi_clean}",
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            return True, data.get("message", {})
        return False, None
    except Exception as e:
        logger.warning("DOI lookup failed for %s: %s", doi_clean, e)
        return False, None


def check_url_accessible(url: str) -> bool:
    """Check if URL returns 2xx (head request)."""
    try:
        r = requests.head(url, timeout=8, allow_redirects=True)
        return 200 <= r.status_code < 400
    except Exception:
        try:
            r = requests.get(url, timeout=8, stream=True)
            return 200 <= r.status_code < 400
        except Exception:
            return False


def normalize_author(a: str) -> str:
    """Normalize author string for comparison."""
    a = re.sub(r"\s+", " ", a.strip())
    return a.lower() if a else ""


class CitationChecker:
    """Check citations for validity, DOI/URL/year/author and suspected fakes."""

    def __init__(self, check_doi_online: bool = True, check_url_online: bool = True):
        self.check_doi_online = check_doi_online
        self.check_url_online = check_url_online

    def check_one(self, raw: str, index: int = 0) -> CitationResult:
        """Check a single citation string."""
        result = CitationResult(
            raw=raw,
            index=index,
            status="valid",
            issues=[],
            suggestions=[],
        )
        result.doi = extract_doi(raw)
        result.year = extract_year(raw)
        result.url = None
        urls = extract_urls(raw)
        if urls:
            result.url = urls[0]

        # Extract authors heuristically (APA: Author, A. A. or BibTeX author field)
        result.authors = self._extract_authors(raw)

        # --- DOI validation ---
        if result.doi:
            if self.check_doi_online:
                found, meta = validate_doi(result.doi)
                result.doi_resolved = found
                if found and meta:
                    titles = meta.get("title") or [""]
                    result.title = titles[0] if titles else None
                    cr_year = meta.get("published-print") or meta.get("published-online") or meta.get("created")
                    if cr_year:
                        parts = cr_year.get("date-parts") or []
                        if parts and len(parts[0]) > 0:
                            result.year = str(parts[0][0])
                if not found:
                    result.issues.append("DOI not found in CrossRef (possible fake or typo).")
                    result.suggestions.append("Verify the DOI at https://doi.org/" + result.doi)
                    result.status = "suspected_fake"
            else:
                result.doi_resolved = None  # not checked
        else:
            result.issues.append("No DOI present.")
            result.suggestions.append("Add a DOI if available to improve verifiability.")

        # --- Year ---
        if not result.year:
            result.issues.append("No publication year detected.")
            result.suggestions.append("Include a 4-digit year (e.g. 2020).")
            if result.status == "valid":
                result.status = "warning"
        else:
            y = int(result.year)
            if y < 1900 or y > 2030:
                result.issues.append(f"Year {result.year} seems implausible.")
                result.suggestions.append("Check the publication year.")
                if result.status == "valid":
                    result.status = "warning"

        # --- URL ---
        if result.url and self.check_url_online:
            result.url_accessible = check_url_accessible(result.url)
            if not result.url_accessible:
                result.issues.append("URL is not accessible (broken or unreachable).")
                result.suggestions.append("Update or remove the URL.")
                if result.status == "valid":
                    result.status = "warning"

        # --- Authors ---
        if not result.authors:
            result.issues.append("No author(s) detected.")
            result.suggestions.append("Add at least one author name.")
            if result.status == "valid":
                result.status = "warning"

        # If we have multiple serious issues, mark invalid
        if result.status == "valid" and len(result.issues) >= 2:
            result.status = "warning"
        if "possible fake" in " ".join(result.issues).lower() or result.status == "suspected_fake":
            result.status = "suspected_fake"

        return result

    def _extract_authors(self, raw: str) -> list[str]:
        """Extract author names from citation text (heuristic)."""
        authors = []
        # BibTeX: author = { ... }
        m = re.search(r"author\s*=\s*[\{\"]([^\}\"]+)[\}\"]", raw, re.I)
        if m:
            names = re.split(r"\s+and\s+|\s*;\s*|\s*,\s*(?=[A-Z]\.)", m.group(1), flags=re.I)
            authors = [n.strip().strip("{}") for n in names if n.strip()]
            return authors
        # APA-style: "Author, A. A., & Author, B. B. (year)"
        m = re.search(r"^([^(]+?)\s*\(\s*\d{4}", raw)
        if m:
            part = m.group(1).strip()
            part = re.sub(r"\s+&\s+", ", ", part)
            names = [n.strip() for n in re.split(r",(?=\s*[A-Z]\.?\s*(?:,|\s+&|$))", part)]
            authors = [n for n in names if len(n) > 2]
        return authors if authors else []

    def check_many(self, citations: list[str]) -> list[CitationResult]:
        """Check a list of citation strings."""
        return [self.check_one(c, i) for i, c in enumerate(citations, 1)]
