"""
Parse citations from pasted text: BibTeX, APA, or unformatted (one per line / numbered).
"""

import re
from typing import List, Tuple

FORMAT_BIBTEX = "bibtex"
FORMAT_APA = "apa"
FORMAT_UNFORMATTED = "unformatted"
FORMAT_UNKNOWN = "unknown"


def detect_format(text: str) -> str:
    """Detect citation format from pasted text."""
    text = text.strip()
    if not text:
        return FORMAT_UNKNOWN
    # BibTeX: @article{...}, @inproceedings{...}, etc.
    if re.search(r"@\s*(?:article|inproceedings|book|incollection|misc)\s*\{", text, re.I):
        return FORMAT_BIBTEX
    # APA-like: Author, A. A. (year). Title. ...
    if re.search(r"\(?\s*19\d{2}\s*\)|\(?\s*20\d{2}\s*\)", text) and re.search(
        r"[A-Z][a-z]+,\s*[A-Z]\.", text
    ):
        return FORMAT_APA
    return FORMAT_UNFORMATTED


def parse_bibtex(text: str) -> List[str]:
    """Parse BibTeX content into list of full entry strings."""
    entries = []
    start = 0
    while True:
        m = re.search(r"@\s*\w+\s*\{[^,]*", text[start:], re.I)
        if not m:
            break
        entry_start = start + m.start()
        depth = 0
        i = start + m.start()
        begun = False
        while i < len(text):
            if text[i] == "{":
                depth += 1
                begun = True
            elif text[i] == "}":
                depth -= 1
                if begun and depth == 0:
                    entries.append(text[entry_start : i + 1].strip())
                    start = i + 1
                    break
            i += 1
        else:
            break
    return entries


def parse_apa_or_unformatted(text: str) -> List[str]:
    """
    Parse APA or unformatted citations. Strategies:
    - Numbered refs: 1. ... 2. ...
    - Line-separated
    - Paragraph-separated (double newline)
    """
    text = text.strip()
    citations = []

    # Numbered list: 1. Citation 2. Citation or [1] ...
    numbered = re.split(r"\n\s*(?:\d+[\.\)]\s*|\[\d+\]\s*)", text)
    numbered = [s.strip() for s in numbered if s.strip() and len(s.strip()) > 20]
    if len(numbered) > 1:
        return numbered

    # Split by double newline (paragraphs)
    paras = [p.strip() for p in text.split("\n\n") if p.strip() and len(p.strip()) > 20]
    if len(paras) > 1:
        return paras

    # Single citation or one per line
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) == 1:
        return [lines[0]] if lines[0] else []
    # Multiple lines: treat each non-empty line as one citation if lines look like full refs
    for ln in lines:
        if len(ln) > 30 and (re.search(r"\d{4}", ln) or re.search(r"doi\.org|10\.\d{4}", ln)):
            citations.append(ln)
        elif len(ln) > 50:
            citations.append(ln)
    if citations:
        return citations
    # Fallback: whole text as one
    if text:
        return [text]
    return []


def parse_citations(text: str) -> Tuple[List[str], str]:
    """
    Parse pasted text into a list of citation strings.
    Returns (list of citation strings, detected format).
    Supports mixed content: e.g. BibTeX block then APA block (split by double newline).
    """
    if not text or not text.strip():
        return [], FORMAT_UNKNOWN
    # Mixed content: split by double newline and parse each block
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if len(blocks) > 1:
        all_citations = []
        for block in blocks:
            fmt = detect_format(block)
            if fmt == FORMAT_BIBTEX:
                all_citations.extend(parse_bibtex(block))
            else:
                all_citations.extend(parse_apa_or_unformatted(block))
        return all_citations, "mixed" if len(set(detect_format(b) for b in blocks)) > 1 else detect_format(blocks[0])
    fmt = detect_format(text)
    if fmt == FORMAT_BIBTEX:
        return parse_bibtex(text), fmt
    return parse_apa_or_unformatted(text), fmt
