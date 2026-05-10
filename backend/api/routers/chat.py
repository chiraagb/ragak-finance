"""Chat session management + SSE streaming AI responses."""
from __future__ import annotations
import uuid
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, constr

from db.session import get_db, AsyncSessionLocal
from db.models.chat import ChatSession, ChatMessage, ToolCallLog
from api.dependencies import get_current_user
from db.models.user import User
from core.config import settings
from core.logging import logger

router = APIRouter(prefix="/api/chat", tags=["chat"])


class SendMessageRequest(BaseModel):
    content: constr(max_length=2000)
    active_profile_id: Optional[str] = None


class CreateSessionRequest(BaseModel):
    session_name: Optional[str] = None
    active_profile_id: Optional[str] = None


@router.post("/sessions", status_code=201)
async def create_session(
    body: CreateSessionRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    thread_id = f"user-{user.id}-{uuid.uuid4()}"
    session = ChatSession(
        user_id=user.id,
        session_name=body.session_name or "New Chat",
        langgraph_thread_id=thread_id,
        active_profile_id=uuid.UUID(body.active_profile_id) if body.active_profile_id else None,
    )
    db.add(session)
    await db.flush()
    return {"session_id": str(session.id), "thread_id": thread_id}


@router.get("/sessions")
async def list_sessions(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChatSession).where(ChatSession.user_id == user.id).order_by(ChatSession.last_active_at.desc()).limit(20)
    )
    sessions = result.scalars().all()
    return [{"id": str(s.id), "name": s.session_name, "last_active": s.last_active_at.isoformat()} for s in sessions]


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    session = await _get_session_or_404(db, session_id, user)
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return [{"id": str(m.id), "role": m.role, "content": m.content, "intent": m.intent, "created_at": m.created_at.isoformat()} for m in messages]


@router.get("/sessions/{session_id}/tools")
async def get_tool_logs(session_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await _get_session_or_404(db, session_id, user)
    result = await db.execute(
        select(ToolCallLog).where(ToolCallLog.session_id == session_id).order_by(ToolCallLog.called_at.desc()).limit(50)
    )
    logs = result.scalars().all()
    return [{"tool": l.tool_name, "latency_ms": l.latency_ms, "called_at": l.called_at.isoformat()} for l in logs]


@router.post("/sessions/{session_id}/messages")
async def send_message(
    request: Request,
    session_id: uuid.UUID,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session_result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id))
    session = session_result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    active_profile_id = body.active_profile_id or (str(session.active_profile_id) if session.active_profile_id else None)

    user_msg = ChatMessage(session_id=session_id, role="user", content=body.content)
    db.add(user_msg)
    await db.commit()

    async def event_stream():
        accumulated = ""
        intent = None
        confidence = None
        sources = []
        error = None

        try:
            from langchain_core.messages import HumanMessage

            async with AsyncSessionLocal() as stream_db:
                from agents.graph import build_graph

                async def _run_graph(checkpointer):
                    nonlocal intent, confidence, sources, accumulated
                    graph = build_graph(db=stream_db, checkpointer=checkpointer)
                    initial_state = {
                        "user_query": body.content,
                        "session_id": str(session_id),
                        "user_id": str(user.id),
                        "active_profile_id": active_profile_id,
                        "extracted_fund_names": [],
                        "extracted_fund_ids": [],
                        "rag_chunks": [],
                        "response_sources": [],
                        "retry_count": 0,
                        "messages": [HumanMessage(content=body.content)],
                    }
                    config = {"configurable": {"thread_id": session.langgraph_thread_id}}
                    async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
                        for node_name, node_output in chunk.items():
                            if node_name == "intent_detector" and isinstance(node_output, dict):
                                intent = node_output.get("intent")
                                yield f"event: tool_call\ndata: {json.dumps({'tool': 'intent_detection', 'intent': intent, 'status': 'done'})}\n\n"
                            if node_name in ("rag_node", "comparison_node", "ranking_node", "risk_node"):
                                yield f"event: tool_call\ndata: {json.dumps({'tool': node_name, 'status': 'running'})}\n\n"
                            if node_name == "context_assembler" and isinstance(node_output, dict):
                                confidence = node_output.get("confidence")
                                sources = node_output.get("response_sources", [])
                            if node_name == "response_synthesizer" and isinstance(node_output, dict):
                                response_text = node_output.get("response", "")
                                for char in response_text:
                                    accumulated += char
                                    yield f"event: token\ndata: {json.dumps({'delta': char})}\n\n"

                try:
                    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                    async with AsyncPostgresSaver.from_conn_string(settings.database_url_sync) as checkpointer:
                        await checkpointer.setup()
                        async for chunk in _run_graph(checkpointer):
                            yield chunk
                except Exception:
                    async for chunk in _run_graph(None):
                        yield chunk

        except Exception as e:
            logger.error("chat_stream_error", error=str(e), session_id=str(session_id))
            error = "I couldn't process your question right now. Please try again."
            yield f"event: token\ndata: {json.dumps({'delta': error})}\n\n"
            accumulated = error

        async with AsyncSessionLocal() as save_db:
            assistant_msg = ChatMessage(
                session_id=session_id,
                role="assistant",
                content=accumulated,
                intent=intent,
            )
            save_db.add(assistant_msg)
            await save_db.commit()

        done_payload = {
            "intent": intent,
            "confidence": confidence,
            "sources": sources[:5],
        }
        yield f"event: done\ndata: {json.dumps(done_payload)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _get_session_or_404(db: AsyncSession, session_id: uuid.UUID, user: User) -> ChatSession:
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
