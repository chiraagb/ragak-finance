"""Response synthesizer: LLM generates the final user-facing explanation."""
from __future__ import annotations
from typing import AsyncGenerator
from agents.state import AgentState
from core.config import settings
from core.logging import logger
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

_SYSTEM_PROMPT = """You are RAGAK, an AI financial assistant for Indian mutual fund investors.

Rules:
- Explain simply and clearly in plain English
- Always cite your sources (e.g., "According to the factsheet...")
- Use Indian context: mention SEBI, AMFI, INR (₹), crores
- NEVER extrapolate beyond the provided data
- NEVER make investment recommendations (say "consult a financial advisor" for decisions)
- If data is missing, say "I don't have that information in the uploaded factsheet"
- Keep responses focused and under 400 words unless comparison/analysis requires more

Formatting (always use markdown):
- Use **bold** for fund names, key metrics, and important figures
- Use ## headings for major sections (e.g., ## Credit Quality, ## Risk Profile)
- Use bullet lists (- item) for enumerating metrics, holdings, or comparison points
- Use tables (| Col | Col |) for side-by-side fund comparisons
- Use > blockquotes for direct factsheet citations
- Use *italics* for disclaimers and caveats
- Never output a wall of plain text — always structure with headings or lists
"""


def _get_llm(streaming: bool = False) -> ChatGoogleGenerativeAI:
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.gemini_api_key,
        temperature=0.3,
        streaming=streaming,
    )


async def response_synthesizer_node(state: AgentState) -> dict:
    query = state["user_query"]
    context = state.get("financial_context", "")
    confidence = state.get("confidence", "low")

    if not context:
        return {
            "response": (
                "I don't have enough factsheet data to answer this question reliably. "
                "Please upload the relevant fund factsheet first, or try a different question."
            )
        }

    try:
        llm = _get_llm()
        response = await llm.ainvoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"FINANCIAL CONTEXT:\n{context}\n\nUser Question: {query}"),
        ])
        answer = response.content

        if confidence == "low":
            answer += "\n\n*Note: Limited factsheet data was available for this response.*"

        return {"response": answer}

    except Exception as e:
        logger.error("response_synthesis_error", error=str(e))
        return {
            "response": "I couldn't process your question right now. Please try again in a moment.",
            "error": str(e),
        }


async def stream_response(state: AgentState) -> AsyncGenerator[str, None]:
    """Streaming version for SSE endpoint."""
    query = state["user_query"]
    context = state.get("financial_context", "")

    if not context:
        yield "I don't have enough factsheet data for this question. Please upload the relevant fund factsheet."
        return

    try:
        llm = _get_llm(streaming=True)
        async for chunk in llm.astream([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"FINANCIAL CONTEXT:\n{context}\n\nUser Question: {query}"),
        ]):
            if chunk.content:
                yield chunk.content

    except Exception as e:
        logger.error("stream_synthesis_error", error=str(e))
        yield "I couldn't process your question right now. Please try again."
