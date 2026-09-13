import re
from pathlib import Path

from .models import Citation

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
URL_RE = re.compile(r"https?://[^\s\])}>\"']+", re.I)
YEAR_RE = re.compile(r"\b(18\d{2}|19\d{2}|20\d{2})\b")


def clean_doi(value: str | None) -> str | None:
    if not value:
        return None
    m = DOI_RE.search(value)
    return m.group(0).rstrip(".,;)").lower() if m else None


def _bib_fields(entry: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = entry.find(",") + 1
    while i > 0 and i < len(entry):
        m = re.search(r"(\w+)\s*=\s*", entry[i:])
        if not m:
            break
        key = m.group(1).lower()
        pos = i + m.end()
        while pos < len(entry) and entry[pos].isspace():
            pos += 1
        if pos >= len(entry):
            break
        if entry[pos] == "{":
            depth = 1
            j = pos + 1
            while j < len(entry) and depth:
                if entry[j] == "{":
                    depth += 1
                elif entry[j] == "}":
                    depth -= 1
                j += 1
            value = entry[pos + 1:j - 1] if depth == 0 else entry[pos + 1:]
            i = j
        elif entry[pos] == '"':
            j = pos + 1
            while j < len(entry) and entry[j] != '"':
                j += 1
            value = entry[pos + 1:j]
            i = j + 1
        else:
            j = entry.find(",", pos)
            if j == -1:
                j = len(entry)
            value = entry[pos:j].strip()
            i = j + 1
        fields[key] = re.sub(r"\s+", " ", value).strip()
    return fields


def parse_bibtex(text: str) -> list[Citation]:
    entries: list[str] = []
    start = None
    depth = 0
    for i, ch in enumerate(text):
        if ch == "@" and start is None:
            start = i
        if start is not None:
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    entries.append(text[start:i + 1])
                    start = None
    out: list[Citation] = []
    for idx, entry in enumerate(entries, 1):
        f = _bib_fields(entry)
        year = int(f["year"]) if f.get("year", "").isdigit() else None
        authors = [x.strip() for x in re.split(r"\s+and\s+", f.get("author", ""), flags=re.I) if x.strip()]
        out.append(Citation(raw=entry, index=idx, title=f.get("title"), authors=authors, year=year,
                            doi=clean_doi(f.get("doi")), venue=f.get("journal") or f.get("booktitle"), url=f.get("url")))
    return out


def parse_ris(text: str) -> list[Citation]:
    blocks = re.split(r"(?m)^ER\s*-\s*$", text)
    out: list[Citation] = []
    for block in blocks:
        if "TY  -" not in block:
            continue
        vals: dict[str, list[str]] = {}
        for line in block.splitlines():
            m = re.match(r"^([A-Z0-9]{2})\s*-\s*(.*)$", line)
            if m:
                vals.setdefault(m.group(1), []).append(m.group(2).strip())
        title = (vals.get("TI") or vals.get("T1") or [None])[0]
        year_s = (vals.get("PY") or vals.get("Y1") or [""])[0]
        ym = YEAR_RE.search(year_s)
        out.append(Citation(raw=block.strip(), index=len(out) + 1, title=title,
                            authors=vals.get("AU", []), year=int(ym.group(1)) if ym else None,
                            doi=clean_doi((vals.get("DO") or [None])[0]),
                            venue=(vals.get("JO") or vals.get("JF") or [None])[0],
                            url=(vals.get("UR") or [None])[0]))
    return out


def split_reference_list(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"(?m)^\s*(?:\[\d+\]|\d+[.)])\s+", text)
    parts = [re.sub(r"\s+", " ", p).strip() for p in parts if len(p.strip()) > 15]
    if len(parts) > 1:
        return parts
    paras = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"\n\s*\n", text) if len(p.strip()) > 15]
    if len(paras) > 1:
        return paras
    lines = [re.sub(r"\s+", " ", p).strip() for p in text.splitlines() if len(p.strip()) > 25]
    return lines or [re.sub(r"\s+", " ", text)]


def parse_reference(raw: str, index: int) -> Citation:
    doi = clean_doi(raw)
    year_m = YEAR_RE.search(raw)
    year = int(year_m.group(1)) if year_m else None
    url_m = URL_RE.search(raw)
    url = url_m.group(0).rstrip(".,;") if url_m else None
    title = None
    if year_m:
        after = raw[year_m.end():].lstrip(" ).,;:-")
        candidate = re.split(r"\.\s+(?=[A-Z])", after, maxsplit=1)[0].strip(" .\"")
        if 5 <= len(candidate) <= 400:
            title = candidate
    if not title:
        quoted = re.search(r"[\"“]([^\"”]{8,300})[\"”]", raw)
        if quoted:
            title = quoted.group(1).strip()
    authors: list[str] = []
    prefix = raw[:year_m.start()] if year_m else raw[:120]
    prefix = re.sub(r"^\s*(?:\[\d+\]|\d+[.)])\s*", "", prefix)
    for token in re.split(r"\s*(?:;|\band\b|&)\s*", prefix, flags=re.I):
        t = token.strip(" ,.")
        if 2 < len(t) < 100 and re.search(r"[A-Za-z]", t):
            authors.append(t)
    return Citation(raw=raw, index=index, title=title, authors=authors[:12], year=year, doi=doi, url=url)


def parse_citations(text: str) -> list[Citation]:
    if re.search(r"@\w+\s*\{", text):
        return parse_bibtex(text)
    if re.search(r"(?m)^TY\s*-", text):
        return parse_ris(text)
    return [parse_reference(raw, i) for i, raw in enumerate(split_reference_list(text), 1)]


def extract_text_from_file(path: str | Path) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader
        return "\n".join((page.extract_text() or "") for page in PdfReader(str(p)).pages)
    if suffix == ".docx":
        from docx import Document
        return "\n".join(x.text for x in Document(str(p)).paragraphs)
    return p.read_text(encoding="utf-8", errors="ignore")


def extract_references_section(text: str) -> str:
    matches = list(re.finditer(r"(?im)^\s*(references|bibliography|works cited)\s*$", text))
    return text[matches[-1].end():].strip() if matches else text
