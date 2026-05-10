"""Classifies PDF page/section content into structured vs. embeddable types.

Structured sections (holdings, returns tables, credit quality, maturity) are routed
to the DB via structured_extractor — they must NOT be embedded.

Embeddable sections (commentary, investment objective, strategy) are chunked and
stored in pgvector for semantic search.
"""
from __future__ import annotations

EMBEDDABLE_SECTIONS = {'commentary', 'investment_objective', 'outlook', 'strategy'}

_SECTION_KEYWORDS: dict[str, list[str]] = {
    'commentary': [
        'fund manager commentary', 'portfolio commentary', 'market review',
        'market commentary', 'fund manager', 'investment outlook', 'market outlook',
        'our view', 'portfolio review', 'month in review',
    ],
    'investment_objective': [
        'investment objective', 'scheme objective', 'investment philosophy',
        'scheme description', 'fund objective',
    ],
    'outlook': [
        'outlook', 'going forward', 'near term', 'medium term',
        'positioning', 'strategy going',
    ],
    'strategy': [
        'investment strategy', 'strategy', 'approach', 'investment approach',
        'portfolio strategy',
    ],
    'holdings': [
        'portfolio holdings', 'top 10 holdings', 'top holdings', 'issuer exposure',
        'portfolio composition', 'securities held', 'top instruments',
        'portfolio breakup', 'scheme portfolio',
    ],
    'sector_allocation': [
        'sector allocation', 'industry allocation', 'sector exposure',
        'industry exposure', 'sector wise', 'asset allocation',
    ],
    'performance': [
        'scheme performance', 'fund performance', 'cagr', 'compounded annual',
        'since inception', 'benchmark returns', 'scheme returns',
        '1 year', '3 year', '5 year',
    ],
    'credit_quality': [
        'credit quality', 'rating profile', 'credit rating', 'issuer quality',
        'quality profile', 'credit breakdown',
    ],
    'maturity_profile': [
        'maturity profile', 'average maturity', 'residual maturity',
        'portfolio maturity', 'weighted average maturity', 'wam',
        'duration profile',
    ],
    'fund_info': [
        'fund details', 'scheme details', 'fund overview', 'about the fund',
        'expense ratio', 'ter', 'fund manager details', 'aum', 'nav',
    ],
}


def classify_section(heading: str, text: str) -> str:
    """Return the section type for a page or section based on heading + text content."""
    combined = (heading + ' ' + text).lower()
    for section_type, keywords in _SECTION_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return section_type
    return 'general'


def is_embeddable(section_type: str) -> bool:
    return section_type in EMBEDDABLE_SECTIONS
