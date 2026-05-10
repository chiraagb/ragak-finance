"""Chat session management + WebSocket streaming AI responses."""
from __future__ import annotations
import uuid
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, constr

from db.session import get_db, AsyncSessionLocal
from db.models.chat import ChatSession, ChatMessage, ToolCallLog
from api.dependencies import get_current_user
from db.models.user import User
from core.config import settings
from core.logging import logger
from core.security import decode_token

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ConnectionManager:
    """Tracks active WebSocket connections per user for future push notifications."""

    def __init__(self):
        # user_id → set of active WebSocket connections
        self.active: dict[str, set[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(user_id, set()).add(ws)

    def disconnect(self, user_id: str, ws: WebSocket):
        self.active.get(user_id, set()).discard(ws)

    async def send_to_user(self, user_id: str, message: dict):
        """Push a notification to all active connections for a user."""
        for ws in list(self.active.get(user_id, set())):
            try:
                await ws.send_json(message)
            except Exception:
                self.active.get(user_id, set()).discard(ws)


manager = ConnectionManager()


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


@router.websocket("/sessions/{session_id}/ws")
async def chat_websocket(
    websocket: WebSocket,
    session_id: uuid.UUID,
    token: str = Query(...),
):
    # Authenticate via query param (browsers can't set WS headers)
    user = await _auth_websocket(token)
    if not user:
        await websocket.close(code=4001)
        return

    await manager.connect(str(user.id), websocket)

    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content", "").strip()
            active_profile_id = data.get("active_profile_id")

            if not content:
                continue

            async with AsyncSessionLocal() as db:
                session_result = await db.execute(
                    select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id)
                )
                session = session_result.scalar_one_or_none()
                if not session:
                    await websocket.send_json({"type": "error", "message": "Session not found"})
                    continue

                active_profile_id = active_profile_id or (str(session.active_profile_id) if session.active_profile_id else None)
                user_msg = ChatMessage(session_id=session_id, role="user", content=content)
                db.add(user_msg)
                await db.commit()

            await _run_and_stream(websocket, session, session_id, user, content, active_profile_id)

    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(str(user.id), websocket)


async def _auth_websocket(token: str) -> Optional[User]:
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
            return result.scalar_one_or_none()
    except Exception:
        return None


async def _run_and_stream(
    websocket: WebSocket,
    session: ChatSession,
    session_id: uuid.UUID,
    user: User,
    content: str,
    active_profile_id: Optional[str],
):
    accumulated = ""
    intent = None
    confidence = None
    sources = []

    try:
        from langchain_core.messages import HumanMessage

        async with AsyncSessionLocal() as stream_db:
            from agents.graph import build_graph

            async def _run_graph(checkpointer):
                nonlocal intent, confidence, sources, accumulated
                graph = build_graph(db=stream_db, checkpointer=checkpointer)
                initial_state = {
                    "user_query": content,
                    "session_id": str(session_id),
                    "user_id": str(user.id),
                    "active_profile_id": active_profile_id,
                    "extracted_fund_names": [],
                    "extracted_fund_ids": [],
                    "rag_chunks": [],
                    "response_sources": [],
                    "retry_count": 0,
                    "messages": [HumanMessage(content=content)],
                }
                config = {"configurable": {"thread_id": session.langgraph_thread_id}}
                async for chunk in graph.astream(initial_state, config=config, stream_mode="updates"):
                    for node_name, node_output in chunk.items():
                        if node_name == "intent_detector" and isinstance(node_output, dict):
                            intent = node_output.get("intent")
                            await websocket.send_json({"type": "tool_call", "tool": "intent_detection", "intent": intent, "status": "done"})
                        if node_name in ("rag_node", "comparison_node", "ranking_node", "risk_node"):
                            await websocket.send_json({"type": "tool_call", "tool": node_name, "status": "running"})
                        if node_name == "context_assembler" and isinstance(node_output, dict):
                            confidence = node_output.get("confidence")
                            sources = node_output.get("response_sources", [])
                        if node_name == "response_synthesizer" and isinstance(node_output, dict):
                            response_text = node_output.get("response", "")
                            for char in response_text:
                                accumulated += char
                                await websocket.send_json({"type": "token", "delta": char})

            try:
                from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
                async with AsyncPostgresSaver.from_conn_string(settings.database_url_sync) as checkpointer:
                    await checkpointer.setup()
                    await _run_graph(checkpointer)
            except Exception:
                await _run_graph(None)

    except Exception as e:
        logger.error("chat_ws_error", error=str(e), session_id=str(session_id))
        accumulated = "I couldn't process your question right now. Please try again."
        await websocket.send_json({"type": "token", "delta": accumulated})

    async with AsyncSessionLocal() as save_db:
        assistant_msg = ChatMessage(session_id=session_id, role="assistant", content=accumulated, intent=intent)
        save_db.add(assistant_msg)
        await save_db.commit()

    await websocket.send_json({"type": "done", "intent": intent, "confidence": confidence, "sources": sources[:5]})


async def _get_session_or_404(db: AsyncSession, session_id: uuid.UUID, user: User) -> ChatSession:
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id, ChatSession.user_id == user.id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
