"""Hybrid semantic + keyword search with Reciprocal Rank Fusion over pgvector."""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from processing.embedder import get_embedding


@dataclass
class RetrievedChunk:
    chunk_id: str
    chunk_text: str
    fund_id: Optional[str]
    fund_name: Optional[str]
    page_number: Optional[int]
    section_type: Optional[str]
    section_heading: Optional[str]
    contains_table: bool
    factsheet_month: Optional[str]
    score: float


def _reciprocal_rank_fusion(
    vector_rows: list,
    keyword_rows: list,
    k: int = 60,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    scores: dict[str, float] = {}
    meta: dict[str, dict] = {}

    for rank, row in enumerate(vector_rows, start=1):
        cid = str(row.id)
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank)
        meta[cid] = dict(row._mapping)

    for rank, row in enumerate(keyword_rows, start=1):
        cid = str(row.id)
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank)
        if cid not in meta:
            meta[cid] = dict(row._mapping)

    sorted_ids = sorted(scores, key=lambda x: scores[x], reverse=True)[:top_k]
    result = []
    for cid in sorted_ids:
        m = meta[cid]
        result.append(RetrievedChunk(
            chunk_id=cid,
            chunk_text=m.get("chunk_text", ""),
            fund_id=str(m["fund_id"]) if m.get("fund_id") else None,
            fund_name=m.get("fund_name"),
            page_number=m.get("page_number"),
            section_type=m.get("section_type"),
            section_heading=m.get("section_heading"),
            contains_table=bool(m.get("contains_table", False)),
            factsheet_month=m.get("factsheet_month"),
            score=round(scores[cid], 6),
        ))
    return result


async def hybrid_search(
    session: AsyncSession,
    query: str,
    fund_ids: Optional[list[uuid.UUID]] = None,
    section_filter: Optional[str] = None,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    """
    Hybrid search: vector cosine similarity + PostgreSQL full-text, fused via RRF.
    Falls back to keyword-only if embedding generation fails.
    """
    embedding = None
    try:
        embedding = await get_embedding(query)
    except Exception:
        pass

    # Build fund_id filter clause — embed UUIDs as literals to avoid asyncpg ::uuid[] cast issues
    if fund_ids:
        ids_literal = ", ".join(f"'{fid}'" for fid in fund_ids)
        fund_filter = f"fund_id = ANY(ARRAY[{ids_literal}]::uuid[])"
    else:
        fund_filter = "TRUE"

    # Build section filter as SQL clause — avoids asyncpg type inference failure on None
    section_clause = f"section_type = '{section_filter}'" if section_filter else "TRUE"

    vector_rows = []
    if embedding is not None:
        # Embed vector as a SQL literal (floats only — safe) to avoid asyncpg :param::vector conflict
        emb_literal = "[" + ",".join(str(x) for x in embedding) + "]"
        vector_sql = text(f"""
            SELECT id, chunk_text, fund_id, fund_name, page_number, section_type,
                   section_heading, contains_table, factsheet_month,
                   1 - (embedding <=> '{emb_literal}'::vector) AS cosine_score
            FROM document_chunks
            WHERE {fund_filter}
              AND {section_clause}
              AND embedding IS NOT NULL
            ORDER BY embedding <=> '{emb_literal}'::vector
            LIMIT 20
        """)
        result = await session.execute(vector_sql)
        vector_rows = result.all()

    keyword_sql = text(f"""
        SELECT id, chunk_text, fund_id, fund_name, page_number, section_type,
               section_heading, contains_table, factsheet_month,
               ts_rank(to_tsvector('english', chunk_text),
                       plainto_tsquery('english', :query)) AS kw_score
        FROM document_chunks
        WHERE {fund_filter}
          AND {section_clause}
          AND to_tsvector('english', chunk_text) @@ plainto_tsquery('english', :query)
        ORDER BY kw_score DESC
        LIMIT 20
    """)
    kw_result = await session.execute(keyword_sql, {"query": query})
    keyword_rows = kw_result.all()

    return _reciprocal_rank_fusion(vector_rows, keyword_rows, top_k=top_k)


def compute_confidence(
    rag_chunks: list[RetrievedChunk],
    data_completeness: float = 1.0,
) -> str:
    """Combine retrieval signals into High/Medium/Low confidence."""
    if not rag_chunks:
        return "low"
    avg_score = sum(c.score for c in rag_chunks) / len(rag_chunks)
    if len(rag_chunks) >= 4 and avg_score > 0.015 and data_completeness >= 0.8:
        return "high"
    if len(rag_chunks) >= 2 and avg_score > 0.005:
        return "medium"
    return "low"
