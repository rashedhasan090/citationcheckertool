from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class Citation:
    raw: str
    index: int = 0
    title: Optional[str] = None
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    context: Optional[str] = None


@dataclass
class Candidate:
    source: str
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: Optional[str] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    is_retracted: bool = False
    source_id: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass
class Evidence:
    source: str
    query: str
    candidates: list[Candidate] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class VerificationResult:
    citation: Citation
    assessment: str
    confidence: int
    matched: Optional[Candidate] = None
    notices: list[str] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)
    source_scores: dict[str, float] = field(default_factory=dict)
    support_score: Optional[int] = None
    support_note: Optional[str] = None
    alternatives: list[Candidate] = field(default_factory=list)
    deep_verified: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
