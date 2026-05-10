"""Financial-domain-aware PDF chunker.

Strategy per text type:
- Section chunks (credit quality, maturity, etc.): single chunk if ≤800 tokens
- Tables: single unit as CSV-like text, tagged contains_table=True
- Large sections: split at row boundaries with 100-token overlap
- Narrative text: sliding window 400 tokens, 80-token overlap

For combined AMC factsheets (e.g. HDFC MF with 100+ schemes), per-page fund name
detection overrides the global fund_name so each chunk is tagged to the correct scheme.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from processing.pdf_extractor import PageContent, detect_section

MAX_SECTION_TOKENS = 800
MAX_CHUNK_TOKENS = 500
OVERLAP_TOKENS = 80
TOKENS_PER_CHAR = 0.25  # approximation: 1 token ≈ 4 chars

# Matches fund name headings in combined factsheets, e.g.:
# "HDFC LIQUID FUND", "SBI OVERNIGHT FUND", "MIRAE ASSET LARGE CAP FUND"
# Requires ALL CAPS, contains FUND or SCHEME, 5–80 chars, not generic AMC headers
_FUND_HEADING_RE = re.compile(
    r'^([A-Z][A-Z0-9 \-&]+(?:FUND|SCHEME|ETF|FoF|FOF)[A-Z0-9 \-&]*)$'
)
_GENERIC_HEADINGS = {
    "MUTUAL FUND", "MUTUAL FUNDS", "FACTSHEET", "FUND OF FUNDS",
    "FUND MANAGER", "FUND DETAILS", "FUND PERFORMANCE",
}


@dataclass
class Chunk:
    chunk_index: int
    chunk_text: str
    page_number: int
    section_type: str
    section_heading: Optional[str]
    contains_table: bool
    fund_name: Optional[str] = None  # per-chunk fund name (overrides doc-level for combined factsheets)


def _approx_tokens(text: str) -> int:
    return max(1, int(len(text) * TOKENS_PER_CHAR))


def _sliding_window(text: str, max_tokens: int = MAX_CHUNK_TOKENS, overlap: int = OVERLAP_TOKENS) -> list[str]:
    max_chars = int(max_tokens / TOKENS_PER_CHAR)
    overlap_chars = int(overlap / TOKENS_PER_CHAR)
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        chunk = text[start:end]
        if len(chunk.strip()) > 50:
            chunks.append(chunk.strip())
        start += max_chars - overlap_chars
    return chunks


def _table_to_text(table_rows: list[list[str]]) -> str:
    lines = []
    for row in table_rows:
        cells = [str(c).strip() if c else "" for c in row]
        lines.append(" | ".join(cells))
    return "\n".join(lines)


def _detect_fund_name_on_page(text: str) -> Optional[str]:
    """Detect a scheme-level fund name heading from the top lines of a page.

    Combined AMC factsheets print the scheme name as an ALL-CAPS heading at the
    start of each scheme's section. We scan the first 10 lines and return the
    first match so downstream chunks are tagged to the correct scheme.
    """
    for line in text.strip().split("\n")[:10]:
        line = line.strip()
        if not line or len(line) < 5 or len(line) > 80:
            continue
        if line.upper() in _GENERIC_HEADINGS:
            continue
        if _FUND_HEADING_RE.match(line):
            return line.title()  # "HDFC LIQUID FUND" → "Hdfc Liquid Fund"
    return None


def chunk_pages(pages: list[PageContent], fund_name: Optional[str] = None, factsheet_month: Optional[str] = None) -> list[Chunk]:
    chunks: list[Chunk] = []
    chunk_idx = 0
    current_fund_name = fund_name  # tracks active scheme for combined factsheets

    def _make_prefix(name: Optional[str]) -> str:
        parts = []
        if name:
            parts.append(f"Fund: {name}")
        if factsheet_month:
            parts.append(f"Month: {factsheet_month}")
        return " | ".join(parts) + "\n\n" if parts else ""

    for page in pages:
        # Override fund name if a scheme heading is detected on this page
        detected = _detect_fund_name_on_page(page.text)
        if detected:
            current_fund_name = detected

        prefix = _make_prefix(current_fund_name)
        section_type = detect_section(page.text)
        section_heading = _extract_heading(page.text)

        if page.has_table and page.table_data:
            for table in page.table_data:
                table_text = prefix + _table_to_text(table)
                chunks.append(Chunk(
                    chunk_index=chunk_idx,
                    chunk_text=table_text,
                    page_number=page.page_number,
                    section_type=section_type,
                    section_heading=section_heading,
                    contains_table=True,
                    fund_name=current_fund_name,
                ))
                chunk_idx += 1

        if not page.text.strip():
            continue

        text_with_prefix = prefix + page.text
        token_count = _approx_tokens(text_with_prefix)

        if token_count <= MAX_SECTION_TOKENS:
            chunks.append(Chunk(
                chunk_index=chunk_idx,
                chunk_text=text_with_prefix.strip(),
                page_number=page.page_number,
                section_type=section_type,
                section_heading=section_heading,
                contains_table=False,
                fund_name=current_fund_name,
            ))
            chunk_idx += 1
        else:
            sub_chunks = _sliding_window(page.text)
            for sub in sub_chunks:
                chunks.append(Chunk(
                    chunk_index=chunk_idx,
                    chunk_text=(prefix + sub).strip(),
                    page_number=page.page_number,
                    section_type=section_type,
                    section_heading=section_heading,
                    contains_table=False,
                    fund_name=current_fund_name,
                ))
                chunk_idx += 1

    return chunks


def _extract_heading(text: str) -> Optional[str]:
    lines = text.strip().split("\n")
    for line in lines[:3]:
        line = line.strip()
        if 3 <= len(line) <= 100 and not line.endswith('.'):
            return line
    return None
