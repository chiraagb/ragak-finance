"""PyMuPDF-based PDF text and table extractor."""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PageContent:
    page_number: int
    text: str
    has_table: bool
    table_data: list[list[str]] = field(default_factory=list)


SECTION_KEYWORDS: dict[str, list[str]] = {
    "credit_quality": ["credit quality", "rating profile", "credit rating", "issuer quality"],
    "maturity_profile": ["maturity profile", "average maturity", "residual maturity", "portfolio maturity"],
    "holdings": ["portfolio holdings", "top holdings", "portfolio composition", "securities held"],
    "performance": ["performance", "returns", "scheme returns", "benchmark returns"],
    "fund_info": ["fund details", "scheme details", "fund overview", "about the fund"],
    "overview": ["portfolio at a glance", "portfolio summary", "key facts"],
}


def extract_pdf(path: str) -> tuple[list[PageContent], str | None, str | None]:
    """
    Extract pages from a PDF. Returns (pages, detected_fund_name, factsheet_month).
    Requires pymupdf installed.
    """
    import fitz  # PyMuPDF

    doc = fitz.open(path)
    pages: list[PageContent] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        text = _clean_text(text)

        tables = []
        has_table = False
        try:
            raw_tables = page.find_tables()
            for tbl in raw_tables:
                rows = tbl.extract()
                if rows:
                    has_table = True
                    tables.append(rows)
        except Exception:
            pass

        pages.append(PageContent(
            page_number=page_num + 1,
            text=text,
            has_table=has_table,
            table_data=tables,
        ))

    doc.close()
    fund_name, month = _detect_fund_meta(pages)
    return pages, fund_name, month


def _clean_text(text: str) -> str:
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()


def _detect_fund_meta(pages: list[PageContent]) -> tuple[str | None, str | None]:
    if not pages:
        return None, None
    first_page_text = pages[0].text

    month = None
    month_patterns = [
        r'(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{4}',
        r'\d{2}/\d{4}',
        r'\d{4}-\d{2}',
    ]
    for pattern in month_patterns:
        m = re.search(pattern, first_page_text, re.IGNORECASE)
        if m:
            month = m.group(0)
            break

    fund_name = None
    fund_patterns = [
        r'(?:axis|hdfc|icici|sbi|kotak|mirae|dsp|nippon|uti|franklin|aditya birla|tata)\s+[\w\s]+\s+(?:fund|scheme)',
    ]
    for pattern in fund_patterns:
        m = re.search(pattern, first_page_text, re.IGNORECASE)
        if m:
            fund_name = m.group(0).strip()
            break

    return fund_name, month


def detect_section(text: str) -> str:
    text_lower = text.lower()
    for section_type, keywords in SECTION_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return section_type
    return "general"
