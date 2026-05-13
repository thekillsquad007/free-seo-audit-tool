from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime


class Severity(Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class Page:
    url: str
    status_code: int
    content: str
    soup: Optional["BeautifulSoup"] = None
    headers: dict = field(default_factory=dict)
    load_time: float = 0.0
    content_type: str = ""


@dataclass
class Issue:
    analyzer: str
    severity: Severity
    message: str
    recommendation: str
    page_url: str
    element: Optional[str] = None
    current_value: Optional[str] = None
    suggested_value: Optional[str] = None

    def to_dict(self):
        return {
            "analyzer": self.analyzer,
            "severity": self.severity.value,
            "message": self.message,
            "recommendation": self.recommendation,
            "page_url": self.page_url,
            "element": self.element,
            "current_value": self.current_value,
            "suggested_value": self.suggested_value,
        }


@dataclass
class AuditResult:
    target_url: str
    total_pages_crawled: int
    issues: list[Issue]
    scores: dict[str, float]
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    crawl_errors: list[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "target_url": self.target_url,
            "total_pages_crawled": self.total_pages_crawled,
            "timestamp": self.timestamp,
            "crawl_errors": self.crawl_errors,
            "scores": self.scores,
            "overall_score": self.overall_score,
            "summary": self.summary,
            "issues": [i.to_dict() for i in self.issues],
        }

    @property
    def overall_score(self):
        if not self.scores:
            return 0.0
        return round(sum(self.scores.values()) / len(self.scores), 1)

    @property
    def issue_count(self):
        return len(self.issues)
