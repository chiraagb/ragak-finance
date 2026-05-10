"""Extract structured financial metrics from factsheet text using regex + optional LLM fallback."""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from processing.pdf_extractor import PageContent

# Reuse same heading pattern as chunker
_FUND_HEADING_RE = re.compile(
    r'^([A-Z][A-Z0-9 \-&]+(?:FUND|SCHEME|ETF|FoF|FOF)[A-Z0-9 \-&]*)$'
)
_GENERIC_HEADINGS = {
    "MUTUAL FUND", "MUTUAL FUNDS", "FACTSHEET", "FUND OF FUNDS",
    "FUND MANAGER", "FUND DETAILS", "FUND PERFORMANCE",
}


def _detect_fund_name_on_page(text: str) -> Optional[str]:
    for line in text.strip().split("\n")[:10]:
        line = line.strip()
        if not line or len(line) < 5 or len(line) > 80:
            continue
        if line.upper() in _GENERIC_HEADINGS:
            continue
        if _FUND_HEADING_RE.match(line):
            return line.title()
    return None


@dataclass
class ExtractedMetrics:
    aaa_pct: Optional[float] = None
    sovereign_pct: Optional[float] = None
    a1plus_pct: Optional[float] = None
    overnight_bucket_pct: Optional[float] = None
    lt7d_bucket_pct: Optional[float] = None
    wam_days: Optional[float] = None
    expense_ratio: Optional[float] = None
    aum_crores: Optional[float] = None
    max_single_issuer_pct: Optional[float] = None
    returns_1y: Optional[float] = None
    returns_3y: Optional[float] = None


def _find_pct(text: str, *patterns: str) -> Optional[float]:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except (IndexError, ValueError):
                pass
    return None


def _find_float(text: str, *patterns: str) -> Optional[float]:
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except (IndexError, ValueError):
                pass
    return None


def extract_metrics_from_pages(pages: list[PageContent]) -> ExtractedMetrics:
    full_text = "\n".join(p.text for p in pages)
    m = ExtractedMetrics()

    m.aaa_pct = _find_pct(full_text,
        r'aaa\s*[:/]?\s*([\d.]+)\s*%',
        r'([\d.]+)\s*%\s*aaa',
        r'aaa\s+equivalent.*?([\d.]+)\s*%',
    )
    m.sovereign_pct = _find_pct(full_text,
        r'sovereign[^%\n]*?([\d.]+)\s*%',
        r'g[-\s]?sec[^%\n]*?([\d.]+)\s*%',
    )
    m.a1plus_pct = _find_pct(full_text,
        r'a1\+[^%\n]*?([\d.]+)\s*%',
        r'([\d.]+)\s*%\s*a1\+',
    )
    m.overnight_bucket_pct = _find_pct(full_text,
        r'overnight[^%\n]*?([\d.]+)\s*%',
        r'([\d.]+)\s*%.*?overnight',
    )
    m.lt7d_bucket_pct = _find_pct(full_text,
        r'[<≤]\s*7\s*days?[^%\n]*?([\d.]+)\s*%',
        r'1[-–]7\s*days?[^%\n]*?([\d.]+)\s*%',
        r'upto\s*7\s*days?[^%\n]*?([\d.]+)\s*%',
    )
    m.wam_days = _find_float(full_text,
        r'weighted\s+average\s+maturity[^:\n]*?[:\s]([\d.]+)\s*days?',
        r'average\s+maturity[^:\n]*?[:\s]([\d.]+)\s*days?',
        r'wam[^:\n]*?[:\s]([\d.]+)\s*days?',
    )
    m.expense_ratio = _find_pct(full_text,
        r'expense\s+ratio[^%\n]*?([\d.]+)\s*%',
        r'ter[^%\n]*?([\d.]+)\s*%',
        r'total\s+expense\s+ratio[^%\n]*?([\d.]+)\s*%',
    )
    m.aum_crores = _find_float(full_text,
        r'aum[^₹\n]*?(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*cr',
        r'net\s+assets?[^₹\n]*?(?:rs\.?|inr|₹)?\s*([\d,]+(?:\.\d+)?)\s*cr',
        r'corpus[^₹\n]*?([\d,]+(?:\.\d+)?)\s*cr',
    )
    m.returns_1y = _find_pct(full_text,
        r'1\s*year[^%\n]*?([\d.]+)\s*%',
        r'12\s*months?[^%\n]*?([\d.]+)\s*%',
    )
    m.returns_3y = _find_pct(full_text,
        r'3\s*year[^%\n]*?([\d.]+)\s*%',
        r'36\s*months?[^%\n]*?([\d.]+)\s*%',
    )

    return m


def extract_metrics_per_scheme(pages: list[PageContent], default_fund_name: Optional[str] = None) -> dict[str, ExtractedMetrics]:
    """Split a combined factsheet into per-scheme page groups and extract metrics for each.

    Returns a dict of {fund_name: ExtractedMetrics}. Falls back to a single entry
    under default_fund_name if no scheme headings are detected (single-fund factsheet).
    """
    # Group pages by scheme name
    groups: dict[str, list[PageContent]] = {}
    current_name = default_fund_name or "__unknown__"

    for page in pages:
        detected = _detect_fund_name_on_page(page.text)
        if detected:
            current_name = detected
        if current_name not in groups:
            groups[current_name] = []
        groups[current_name].append(page)

    # If only one group and it's unknown, treat as single-fund factsheet
    if list(groups.keys()) == ["__unknown__"] and default_fund_name:
        groups[default_fund_name] = groups.pop("__unknown__")

    return {name: extract_metrics_from_pages(pg) for name, pg in groups.items()}
