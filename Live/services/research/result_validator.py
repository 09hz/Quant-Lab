from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

@dataclass(frozen=True)
class ValidationResult:
    status: str
    confidence: str
    message: str
    http_status: int | None = None
    final_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        return self.status in {"ok", "manual-search"}

def validate_research_url(url: str, *, timeout: float = 8, user_agent: str = "AlgoTraderResearch/0.1 local-newsroom-validator", fetch: bool = False) -> ValidationResult:
    url = str(url or "").strip()
    if not url:
        return ValidationResult(status="failed", confidence="failed", message="Missing URL.")
    if not (url.startswith("https://") or url.startswith("http://")):
        return ValidationResult(status="failed", confidence="failed", message="URL must start with http:// or https://.")
    if not fetch:
        return ValidationResult(status="manual-search", confidence="manual-search", message="Not network-validated. Open the link or enable validation to verify live availability.", final_url=url)
    try:
        request = Request(url, method="GET", headers={"User-Agent": user_agent})
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 200))
            final_url = response.geturl()
            sample = response.read(4096).decode("utf-8", errors="ignore").lower()
        if status >= 400:
            return ValidationResult(status="failed", confidence="failed", message=f"HTTP {status}", http_status=status, final_url=final_url)
        not_found_markers = ["page not found", "404", "not found", "does not exist"]
        if any(marker in sample for marker in not_found_markers):
            return ValidationResult(status="failed", confidence="failed", message="The page appears to contain a not-found marker.", http_status=status, final_url=final_url)
        return ValidationResult(status="ok", confidence="medium", message="HTTP check succeeded.", http_status=status, final_url=final_url)
    except HTTPError as exc:
        return ValidationResult(status="failed", confidence="failed", message=f"HTTP error {exc.code}", http_status=int(exc.code), final_url=url)
    except URLError as exc:
        return ValidationResult(status="failed", confidence="failed", message=f"URL error: {exc.reason}", final_url=url)
    except Exception as exc:
        return ValidationResult(status="failed", confidence="failed", message=f"Validation failed: {exc}", final_url=url)
