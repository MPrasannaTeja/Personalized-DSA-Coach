"""
LangGraph-based DSA Coach Agent.

Graph topology
--------------
START
  └─► coach_node          (LLM decides: respond OR call a tool)
          ├─► tools_node  (executes the tool, returns result)
          │       └─► coach_node  (LLM sees result, decides next step)
          └─► END         (LLM responded without tool call)

State
-----
messages        : full conversation history (HumanMessage / AIMessage / ToolMessage)
user_id         : current user UUID
context_block   : JSON string of student progress (injected per-turn)
rag_context     : relevant past notes fetched before the coach node runs
"""

import json
import logging
from typing import Annotated, Any

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from app.agent.prompts.coach_prompts import COACH_SYSTEM, PHASES
from app.agent.tools.coach_tools import ALL_TOOLS
from app.services.llm import get_llm
from app.services.vector_store import query_similar_notes

# Pre-convert all tools to OpenAI-compatible JSON schema format.
# GROQ's API expects {"type": "function", "function": {"name": ..., "description": ...,
# "parameters": ...}} — passing pre-formatted dicts to bind_tools() bypasses
# LangChain's internal schema conversion, which produces a malformed format that
# GROQ rejects with a 400 tool_use_failed error.
GROQ_TOOL_SCHEMAS = [convert_to_openai_tool(t) for t in ALL_TOOLS]

logger = logging.getLogger(__name__)


# ── Graph state ───────────────────────────────────────────────────────────────

class CoachState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    user_id: str
    context_block: str      # JSON progress summary, refreshed each turn
    rag_context: str        # Formatted past notes for system prompt injection


# ── Helper: build context block ───────────────────────────────────────────────

def _build_context_block(
    user_id: str,
    phase_idx: int,
    topic_idx: int,
    streak: int,
    total_solved: int,
    topic_stats: dict[str, Any],
) -> str:
    try:
        phase = PHASES[phase_idx]
        topic = phase["topics"][topic_idx]
    except IndexError:
        return json.dumps({"error": "invalid phase/topic index"})

    solved = topic_stats.get("total_solved", 0)
    min_needed = topic.get("min_problems", 10)
    clean_rate = (
        topic_stats.get("clean_solve_count", 0) / solved if solved > 0 else 0
    )
    hint_rate = (
        topic_stats.get("hint_used_count", 0) / solved if solved > 0 else 0
    )

    # Dynamic difficulty recommendation
    if clean_rate > 0.7 and hint_rate < 0.3 and solved >= 5:
        rec_difficulty = "hard"
        rec_count = 3
        pace_msg = "Flying through this topic — push harder."
    elif clean_rate > 0.5 and solved >= 3:
        rec_difficulty = "medium"
        rec_count = 2
        pace_msg = "Solid pace. Maintain consistency."
    else:
        rec_difficulty = "easy"
        rec_count = 1
        pace_msg = "Focus on pattern understanding before speed."

    return json.dumps({
        "user_id": user_id,
        "current_phase": phase["title"],
        "current_topic": topic["name"],
        "topic_patterns": topic["patterns"],
        "problems_solved_this_topic": solved,
        "min_required": min_needed,
        "topic_complete": solved >= min_needed,
        "streak_days": streak,
        "total_problems": total_solved,
        "clean_solve_rate": round(clean_rate, 2),
        "hint_rate": round(hint_rate, 2),
        "recommended_difficulty": rec_difficulty,
        "recommended_count": rec_count,
        "coach_pace_note": pace_msg,
    }, indent=2)


# ── Nodes ─────────────────────────────────────────────────────────────────────

async def coach_node(state: CoachState, config: RunnableConfig) -> dict:
    """
    The main LLM node. Builds the system prompt with fresh context + RAG,
    then invokes the LLM (with tools bound). The LLM either:
      - Returns a direct response → graph goes to END
      - Returns tool_calls       → graph goes to tools_node
    """
    llm = get_llm()
    # Bind pre-converted OpenAI-format tool schemas so GROQ receives the correct
    # {"type": "function", "function": {...}} structure it expects natively.
    llm_with_tools = llm.bind_tools(GROQ_TOOL_SCHEMAS)

    system_message = SystemMessage(
        content=COACH_SYSTEM.format(
            context_block=state["context_block"],
            rag_context=state["rag_context"] or "No past notes found yet.",
        )
    )

    # Prepend fresh system message each turn (LangGraph accumulates human/AI turns)
    messages_to_send = [system_message] + state["messages"]

    response: AIMessage = await llm_with_tools.ainvoke(messages_to_send, config)
    logger.debug("Coach node response: tool_calls=%s", bool(response.tool_calls))

    return {"messages": [response]}


async def rag_prefetch_node(state: CoachState, config: RunnableConfig) -> dict:
    """
    Runs BEFORE coach_node on every turn.
    Looks at the last human message and fetches semantically similar past notes
    so the coach can tailor hints to the student's specific blind spots.
    """
    if not state["messages"]:
        return {"rag_context": ""}

    last_human = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "content") and not isinstance(msg, AIMessage):
            last_human = str(msg.content)
            break

    if not last_human:
        return {"rag_context": ""}

    # Extract topic_id from context_block
    try:
        ctx = json.loads(state["context_block"])
        topic_id = ctx.get("current_topic", "")
    except (json.JSONDecodeError, KeyError):
        topic_id = ""

    try:
        notes = await query_similar_notes(
            user_id=state["user_id"],
            query_text=last_human,
            topic_id=None,   # Search all topics for broader context
            n_results=3,
        )
    except Exception as exc:
        logger.warning("RAG prefetch failed: %s", exc)
        notes = []

    if not notes:
        return {"rag_context": ""}

    formatted = "## Relevant past notes from this student:\n\n"
    for i, note in enumerate(notes, 1):
        formatted += (
            f"{i}. **Pattern**: {note['pattern_name']} | **Topic**: {note['topic_id']}\n"
            f"   {note['document'][:300]}...\n\n"
        )

    # Blind spots
    from collections import Counter
    patterns: Counter = Counter(n["pattern_name"] for n in notes if n.get("pattern_name"))
    recurring = [p for p, c in patterns.items() if c >= 2]
    if recurring:
        formatted += f"⚠️ **Recurring blind spots**: {', '.join(recurring)}\n"

    return {"rag_context": formatted}


def should_continue(state: CoachState) -> str:
    """Edge condition: did the LLM request a tool call?"""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return END


# ── Graph construction ────────────────────────────────────────────────────────

def build_coach_graph() -> StateGraph:
    graph = StateGraph(CoachState)

    # Nodes
    graph.add_node("rag_prefetch", rag_prefetch_node)
    graph.add_node("coach", coach_node)
    graph.add_node("tools", ToolNode(tools=ALL_TOOLS))

    # Edges
    graph.add_edge(START, "rag_prefetch")
    graph.add_edge("rag_prefetch", "coach")
    graph.add_conditional_edges("coach", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "coach")   # After tool execution, re-enter coach

    return graph.compile()

def get_coach_graph():
    return build_coach_graph()
