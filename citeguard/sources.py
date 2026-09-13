import html
import re
import xml.etree.ElementTree as ET
from urllib.parse import quote

import requests

from .models import Candidate, Evidence
from .parsers import clean_doi

UA = "CiteGuard/3.0 (research-integrity citation verification; https://github.com/rashedhasan090/citationcheckertool)"


def _year(v):
    try:
        return int(v) if v else None
    except (TypeError, ValueError):
        return None


def _openalex_abstract(inv):
    if not inv:
        return None
    positions = [(i, word) for word, idxs in inv.items() for i in idxs]
    positions.sort()
    return " ".join(word for _, word in positions)


def _crossref_updates(x):
    updates = []
    for key in ("update-to", "updated-by"):
        for item in x.get(key, []) or []:
            label = item.get("label") or item.get("type") or "update"
            if item.get("source"):
                label = f"{label} ({item['source']})"
            updates.append(label)
    return updates


class ScholarlySources:
    def __init__(self, timeout: int = 12, mailto: str | None = None):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": UA, "Accept": "application/json"})
        self.mailto = mailto

    def _get(self, url, **kwargs):
        r = self.session.get(url, timeout=self.timeout, **kwargs)
        r.raise_for_status()
        return r

    def crossref(self, query: str, doi: str | None = None, limit: int = 5) -> Evidence:
        try:
            if doi:
                items = [self._get(f"https://api.crossref.org/works/{quote(doi, safe='')}").json().get("message", {})]
                q = f"doi:{doi}"
            else:
                params = {"query.bibliographic": query, "rows": limit}
                if self.mailto:
                    params["mailto"] = self.mailto
                items = self._get("https://api.crossref.org/works", params=params).json().get("message", {}).get("items", [])
                q = query
            out = []
            for x in items:
                dates = x.get("published-print") or x.get("published-online") or x.get("created") or {}
                parts = dates.get("date-parts", [[None]])
                authors = [" ".join(filter(None, [a.get("given"), a.get("family")])).strip() for a in x.get("author", [])]
                updates = _crossref_updates(x)
                out.append(Candidate(
                    source="Crossref", title=(x.get("title") or [""])[0], authors=authors,
                    year=_year(parts[0][0] if parts and parts[0] else None), doi=clean_doi(x.get("DOI")),
                    venue=(x.get("container-title") or [None])[0], url=x.get("URL"),
                    is_retracted=any("retract" in u.lower() for u in updates), integrity_updates=updates,
                    citation_count=x.get("is-referenced-by-count"), publication_type=x.get("type"),
                    publisher=x.get("publisher"), source_id=x.get("DOI"), raw=x))
            return Evidence("Crossref", q, out)
        except Exception as e:
            return Evidence("Crossref", query, error=str(e))

    def openalex(self, query: str, doi: str | None = None, limit: int = 5) -> Evidence:
        try:
            if doi:
                items = [self._get("https://api.openalex.org/works/https://doi.org/" + quote(doi, safe="/:")).json()]
                q = f"doi:{doi}"
            else:
                params = {"search": query, "per-page": limit}
                if self.mailto:
                    params["mailto"] = self.mailto
                items = self._get("https://api.openalex.org/works", params=params).json().get("results", [])
                q = query
            out = []
            for x in items:
                loc = x.get("primary_location") or {}
                source = loc.get("source") or {}
                ids = x.get("ids") or {}
                oa = x.get("open_access") or {}
                best_oa = x.get("best_oa_location") or {}
                out.append(Candidate(
                    source="OpenAlex", title=x.get("title") or "",
                    authors=[a.get("author", {}).get("display_name", "") for a in x.get("authorships", [])],
                    year=_year(x.get("publication_year")), doi=clean_doi(ids.get("doi") or x.get("doi")),
                    venue=source.get("display_name"), url=loc.get("landing_page_url") or ids.get("openalex"),
                    abstract=_openalex_abstract(x.get("abstract_inverted_index")), is_retracted=bool(x.get("is_retracted")),
                    citation_count=x.get("cited_by_count"), is_open_access=oa.get("is_oa"),
                    oa_url=best_oa.get("pdf_url") or best_oa.get("landing_page_url"), publication_type=x.get("type"),
                    source_id=x.get("id"), raw=x))
            return Evidence("OpenAlex", q, out)
        except Exception as e:
            return Evidence("OpenAlex", query, error=str(e))

    def semantic_scholar(self, query: str, doi: str | None = None, limit: int = 5) -> Evidence:
        fields = "title,authors,year,venue,url,externalIds,abstract,publicationTypes,citationCount,influentialCitationCount,openAccessPdf"
        try:
            if doi:
                items = [self._get(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{quote(doi, safe='')}", params={"fields": fields}).json()]
                q = f"doi:{doi}"
            else:
                items = self._get("https://api.semanticscholar.org/graph/v1/paper/search", params={"query": query, "limit": limit, "fields": fields}).json().get("data", [])
                q = query
            out = []
            for x in items:
                ext, oa = x.get("externalIds") or {}, x.get("openAccessPdf") or {}
                pub_types = x.get("publicationTypes") or []
                out.append(Candidate(
                    source="Semantic Scholar", title=x.get("title") or "", authors=[a.get("name", "") for a in x.get("authors", [])],
                    year=_year(x.get("year")), doi=clean_doi(ext.get("DOI")), venue=x.get("venue"), url=x.get("url"),
                    abstract=x.get("abstract"), citation_count=x.get("citationCount"), influential_citation_count=x.get("influentialCitationCount"),
                    is_open_access=bool(oa.get("url")), oa_url=oa.get("url"), publication_type=", ".join(pub_types[:3]) if pub_types else None,
                    source_id=x.get("paperId"), raw=x))
            return Evidence("Semantic Scholar", q, out)
        except Exception as e:
            return Evidence("Semantic Scholar", query, error=str(e))

    def pubmed(self, query: str, limit: int = 5) -> Evidence:
        try:
            ids = self._get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params={"db": "pubmed", "term": query, "retmode": "json", "retmax": limit}).json().get("esearchresult", {}).get("idlist", [])
            if not ids:
                return Evidence("PubMed", query, [])
            data = self._get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi", params={"db": "pubmed", "id": ",".join(ids), "retmode": "json"}).json().get("result", {})
            out = []
            for pid in ids:
                x = data.get(pid, {})
                articleids = {a.get("idtype"): a.get("value") for a in x.get("articleids", [])}
                year_m = re.search(r"\b(18\d{2}|19\d{2}|20\d{2})\b", x.get("pubdate", ""))
                out.append(Candidate(source="PubMed", title=html.unescape(x.get("title") or ""),
                    authors=[a.get("name", "") for a in x.get("authors", [])], year=_year(year_m.group(1) if year_m else None),
                    doi=clean_doi(articleids.get("doi")), venue=x.get("fulljournalname"), url=f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
                    publication_type="; ".join(x.get("pubtype", [])[:3]) if x.get("pubtype") else None, source_id=pid, raw=x))
            return Evidence("PubMed", query, out)
        except Exception as e:
            return Evidence("PubMed", query, error=str(e))

    def arxiv(self, query: str, limit: int = 5) -> Evidence:
        try:
            root = ET.fromstring(self._get("https://export.arxiv.org/api/query", params={"search_query": f'all:"{query}"', "start": 0, "max_results": limit}).text)
            ns = {"a": "http://www.w3.org/2005/Atom"}
            out = []
            for e in root.findall("a:entry", ns):
                published = e.findtext("a:published", default="", namespaces=ns)
                url = e.findtext("a:id", default=None, namespaces=ns)
                out.append(Candidate(source="arXiv", title=re.sub(r"\s+", " ", e.findtext("a:title", default="", namespaces=ns)).strip(),
                    authors=[a.findtext("a:name", default="", namespaces=ns) for a in e.findall("a:author", ns)], year=_year(published[:4]),
                    venue="arXiv", url=url, abstract=re.sub(r"\s+", " ", e.findtext("a:summary", default="", namespaces=ns)).strip(),
                    is_open_access=True, oa_url=url, publication_type="preprint", source_id=url))
            return Evidence("arXiv", query, out)
        except Exception as e:
            return Evidence("arXiv", query, error=str(e))

    def openlibrary(self, query: str, limit: int = 5) -> Evidence:
        try:
            docs = self._get("https://openlibrary.org/search.json", params={"q": query, "limit": limit}).json().get("docs", [])
            out = [Candidate(source="Open Library", title=x.get("title") or "", authors=x.get("author_name", [])[:8],
                year=_year(x.get("first_publish_year")), venue="Book", url=("https://openlibrary.org" + x.get("key", "")) if x.get("key") else None,
                publication_type="book", publisher=(x.get("publisher") or [None])[0], source_id=x.get("key"), raw=x) for x in docs]
            return Evidence("Open Library", query, out)
        except Exception as e:
            return Evidence("Open Library", query, error=str(e))
