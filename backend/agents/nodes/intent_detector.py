"""Intent detection node: classifies query and extracts fund names."""
from __future__ import annotations
import json
import re
from agents.state import AgentState
from core.config import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

_INTENT_SYSTEM_PROMPT = """You are a financial intent classifier for an Indian mutual fund analysis platform.

Classify the user query into exactly one intent:
- fund_search: User wants to find or discover funds (e.g., "which liquid fund is best")
- comparison: User wants to compare 2+ specific funds
- rag_explain: User wants explanation from factsheet (e.g., "explain this fund's credit quality")
- ranking: User wants ranked list by some criteria
- risk_analysis: User asks about risk, credit quality, liquidity risk
- nav_lookup: User asks for current NAV or price
- general: General financial concept question

Also extract any fund names mentioned (AMC + fund type, e.g. "HDFC Liquid Fund").

Respond in JSON only:
{
  "intent": "<intent>",
  "fund_names": ["<fund name>", ...],
  "confidence": 0.0-1.0
}"""

# Offline fallback keyword classifier (no API cost)
_KEYWORD_MAP = {
    "fund_search": ["which fund", "best fund", "recommend fund", "liquid fund", "safest fund", "top fund"],
    "comparison": ["compare", "vs ", "versus", "better than", "difference between"],
    "rag_explain": ["explain", "what is", "tell me about", "describe", "how does", "meaning of"],
    "ranking": ["rank", "ranked", "ranking", "top 5", "top 10", "best performing"],
    "risk_analysis": ["risk", "credit quality", "liquidity risk", "maturity", "safe", "volatile"],
    "nav_lookup": ["nav", "price", "current value", "unit price"],
}


def _keyword_intent(query: str) -> str:
    q_lower = query.lower()
    for intent, keywords in _KEYWORD_MAP.items():
        if any(kw in q_lower for kw in keywords):
            return intent
    return "general"


def _extract_fund_names_regex(query: str) -> list[str]:
    amcs = r"(?:hdfc|icici|sbi|kotak|mirae|dsp|nippon|uti|franklin|aditya birla|tata|axis|sundaram|invesco|canara|baroda)"
    pattern = rf"({amcs}[\w\s]+?(?:liquid|overnight|ultra short|low duration|money market)\s*fund)"
    matches = re.findall(pattern, query, re.IGNORECASE)
    return [m.strip() for m in matches]


def _get_llm() -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0,
    )


async def intent_detector_node(state: AgentState) -> dict:
    query = state["user_query"]

    try:
        llm = _get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=_INTENT_SYSTEM_PROMPT),
            HumanMessage(content=f"User query: {query}"),
        ])
        data = json.loads(response.content)
        intent = data.get("intent", "general")
        fund_names = data.get("fund_names", [])
    except Exception:
        intent = _keyword_intent(query)
        fund_names = _extract_fund_names_regex(query)

    return {
        "intent": intent,
        "extracted_fund_names": fund_names,
        "extracted_fund_ids": [],
    }
