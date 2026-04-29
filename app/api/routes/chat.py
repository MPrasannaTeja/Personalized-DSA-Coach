"""
/chat endpoint — routes user messages through the LangGraph coach agent.

The endpoint is stateless on the HTTP side: conversation history is
passed in by the caller. For a real production app you'd store history
server-side (Redis / Postgres) keyed by session_id. The structure below
makes that easy to add.
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.agent.coach_graph import _build_context_block, get_coach_graph
from app.api.schemas import ChatRequest, ChatResponse
from app.db.session import AsyncSession, get_async_session
from app.services.progress_service import get_user_by_id, get_user_profile

router = APIRouter(prefix="/chat", tags=["Chat"])
logger = logging.getLogger(__name__)


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    db: AsyncSession = Depends(get_async_session),
) -> ChatResponse:
    """
    Send a message to the DSA coach agent and receive a reply.

    The agent has access to tools (validate_notes, log_problem, etc.)
    and will call them autonomously when appropriate.
    """
    # 1. Validate user exists
    user = await get_user_by_id(db, body.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {body.user_id} not found. Create the user first.",
        )

    # 2. Build context block (live DB snapshot)
    if body.context_override:
        context_block = json.dumps(body.context_override)
    else:
        profile = await get_user_profile(body.user_id)
        topic_stats = profile["topic_stats"]
        # Find current topic stats
        from app.agent.prompts.coach_prompts import PHASES
        try:
            topic = PHASES[user.current_phase_idx]["topics"][user.current_topic_idx]
            current_topic_stats = topic_stats.get(topic["id"], {})
        except (IndexError, KeyError):
            current_topic_stats = {}

        context_block = _build_context_block(
            user_id=body.user_id,
            phase_idx=user.current_phase_idx,
            topic_idx=user.current_topic_idx,
            streak=user.streak,
            total_solved=user.total_problems_solved,
            topic_stats=current_topic_stats,
        )

    # 3. Invoke LangGraph agent
    graph = get_coach_graph()
    initial_state = {
        "messages": [HumanMessage(content=body.message)],
        "user_id": body.user_id,
        "context_block": context_block,
        "rag_context": "",  # will be populated by rag_prefetch_node
    }

    try:
        final_state = await graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("LangGraph invocation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent encountered an error. Please try again.",
        )

    # 4. Extract reply and tool calls made
    reply_text = ""
    tool_calls_made: list[str] = []

    for msg in final_state["messages"]:
        if isinstance(msg, AIMessage):
            if msg.tool_calls:
                tool_calls_made.extend(tc["name"] for tc in msg.tool_calls)
            if msg.content:
                reply_text = str(msg.content)  # last AI text wins
        elif isinstance(msg, ToolMessage):
            pass  # tool results are consumed by the agent, not exposed directly

    if not reply_text:
        reply_text = "I processed your request. Let me know if you need anything else."

    return ChatResponse(
        reply=reply_text,
        tool_calls_made=list(set(tool_calls_made)),
        context_snapshot=json.loads(context_block),
    )
