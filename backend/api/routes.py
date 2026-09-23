import json
import uuid
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from graph.state import AgentState
from graph.workflow import app_graph, run_config, NODE_BY_ACTION
from schemas.schemas import (
    ChatMessageRequest,
    ProfileUpdateRequest,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionStateResponse,
    UserProfileData,
)

router = APIRouter()


def _initial_state(session_id: str, profile: UserProfileData) -> AgentState:
    """Full runtime state seeded once, at session creation."""
    return {
        "session_id": session_id,
        "user_profile": profile,
        "user_query": "",
        "messages": [],
        "selected_tools": [],
        "bmi_data": None,
        "water_data": None,
        "macro_data": None,
        "diet_plan": None,
        "workout_plan": None,
        "gym_data": None,
        "general_response": None,
        "retry_count": 0,
        "current_errors": [],
        "final_report": None,
        # Plan + execution loop (reset by the planner every turn)
        "goal": None,
        "success_criteria": None,
        "plan": None,
        "plan_version": 0,
        "plan_errors": [],
        "current_task": None,
        "completed_tasks": [],
        "failed_tasks": [],
        "action_history": [],
        "tool_results": {},
        "agent_results": {},
        "last_observation": None,
        "execution_steps": 0,
        "next_action": None,
        # Evaluator / replanner
        "evaluation": None,
        "final_status": None,
        "goal_completed": False,
        "replan_required": False,
        "replan_reason": None,
        "replan_count": 0,
        "replan_feedback": None,
        # Task-level validation / per-turn budget
        "task_validation": {},
        "best_results": {},
        "constraints": {},
        "handoff_reason": None,
        "turn_halt": None,
        "llm_calls": 0,
        "llm_tokens": 0,
    }


def _turn_data(state: Dict[str, Any], action: str, key: str) -> Optional[Any]:
    """This turn's value for an action: its best result, else the raw result."""
    best = (state.get("best_results") or {}).get(action) or {}
    value = (best.get("result") or {}).get(key)
    if value is None:
        value = ((state.get("tool_results") or {}).get(action) or {}).get(key)
    return value


def _get_session_values(session_id: str) -> Dict[str, Any]:
    """Restore checkpointed state for a session, or 404 if it doesn't exist."""
    snapshot = app_graph.get_state(run_config(session_id))
    if not snapshot or not snapshot.values:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    return snapshot.values


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/sessions", response_model=SessionCreateResponse)
async def create_session(payload: Optional[SessionCreateRequest] = None):
    """Create a new runtime session and return its session_id (== LangGraph thread_id)."""
    session_id = str(uuid.uuid4())
    profile = (payload.profile if payload and payload.profile else UserProfileData())

    app_graph.update_state(run_config(session_id), _initial_state(session_id, profile))

    return SessionCreateResponse(session_id=session_id, profile=profile)


@router.patch("/sessions/{session_id}/profile", response_model=SessionCreateResponse)
async def update_profile(session_id: str, payload: ProfileUpdateRequest):
    """Merge only the supplied profile fields into the session's runtime state."""
    values = _get_session_values(session_id)
    existing_profile: UserProfileData = values.get("user_profile") or UserProfileData()

    updates = payload.model_dump(exclude_unset=True)
    merged_profile = existing_profile.model_copy(update=updates)

    state_update: Dict[str, Any] = {"user_profile": merged_profile}
    if merged_profile.model_dump() != existing_profile.model_dump():
        # Derived numbers from the old profile are stale now; drop them so
        # later turns (e.g. a diet reading macro_data) can't reuse them.
        state_update.update({"bmi_data": None, "water_data": None, "macro_data": None})

    app_graph.update_state(run_config(session_id), state_update)

    return SessionCreateResponse(session_id=session_id, profile=merged_profile)


@router.post("/sessions/{session_id}/chat/stream")
async def chat_stream(session_id: str, payload: ChatMessageRequest):
    """Stream LLM output as SSE while the LangGraph workflow runs for this session.

    Only the new message is sent in; user_profile and prior messages are
    restored from the session's LangGraph checkpoint (thread_id == session_id).
    """
    _get_session_values(session_id)  # 404 early if the session doesn't exist
    config = run_config(session_id)

    # Only the new message goes in. Everything else (profile, history, last
    # known tool data) is restored from the checkpoint, and the planner
    # resets the per-turn plan/counters/results itself.
    turn_input: Dict[str, Any] = {
        "user_query": payload.message,
        "messages": [{"role": "user", "content": payload.message}],
    }

    async def event_generator() -> AsyncIterator[str]:
        try:
            yield sse("start", {"session_id": session_id})

            final_output = None
            current_node = None

            async for event in app_graph.astream_events(turn_input, config=config, version="v2"):
                event_type = event.get("event")
                metadata = event.get("metadata") or {}
                node = metadata.get("langgraph_node")

                if node and node != current_node:
                    current_node = node
                    if node == "planner":
                        yield sse("planning", {"node": node})
                    elif node in NODE_BY_ACTION.values():
                        yield sse("executing", {"node": node})
                        if node in {"general_worker", "diet_worker", "workout_worker", "gym_worker"}:
                            yield sse("stage", {"node": node})
                    elif node == "evaluator":
                        yield sse("evaluating", {"node": node})
                    elif node == "replanner":
                        yield sse("replanning", {"node": node})

                # Stream only user-facing worker tokens. Planner/executor/
                # evaluator/replanner output is internal control data.
                if event_type == "on_chat_model_stream" and node in {
                    "general_worker", "diet_worker", "workout_worker", "gym_worker"
                }:
                    chunk = event.get("data", {}).get("chunk")
                    content = getattr(chunk, "content", None)
                    if isinstance(content, str) and content:
                        yield sse("token", {"content": content})

                if event_type == "on_chain_end" and node == "__start__":
                    continue

                if event_type == "on_chain_end" and node == "aggregator":
                    output = event.get("data", {}).get("output")
                    if isinstance(output, dict) and output.get("final_report"):
                        final_output = output

            if final_output is None:
                raise RuntimeError("Streaming run ended without a final report.")

            if not final_output.get("final_report"):
                raise RuntimeError("Engine failed to consolidate the final report.")

            # The aggregator's delta only carries final_report/messages; read
            # status and this turn's results from the merged state.
            final_state = app_graph.get_state(config).values
            final_status = final_state.get("final_status") or "incomplete"
            goal_completed = bool(final_state.get("goal_completed")) and final_status == "success"

            yield sse("completed", {"goal_completed": goal_completed, "status": final_status})

            yield sse("done", {
                "status": final_status,
                "session_id": session_id,
                "bmi_data": _turn_data(final_state, "bmi", "bmi_data"),
                "water_data": _turn_data(final_state, "water", "water_data"),
                "macro_data": _turn_data(final_state, "macros", "macro_data"),
                "final_report": final_output["final_report"],
                "goal_completed": goal_completed,
                "plan_version": final_state.get("plan_version", 0),
                "replan_count": final_state.get("replan_count", 0),
                "issues": (final_state.get("evaluation") or {}).get("issues") or [],
            })

        except Exception as e:
            detail = str(e)
            if "rate_limit" in detail.lower() or "tokens per minute" in detail.lower() or "error code: 429" in detail.lower():
                detail = "The coach is temporarily busy because the AI token limit was reached. Please try again in a few seconds."
            yield sse("error", {"status": "error", "detail": detail})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}/state", response_model=SessionStateResponse)
async def get_session_state(session_id: str):
    """Development/debugging endpoint: current runtime state for a session."""
    values = _get_session_values(session_id)

    return SessionStateResponse(
        session_id=session_id,
        profile=values.get("user_profile") or UserProfileData(),
        selected_tools=values.get("selected_tools") or [],
        bmi_data=values.get("bmi_data"),
        water_data=values.get("water_data"),
        macro_data=values.get("macro_data"),
        diet_plan=values.get("diet_plan"),
        workout_plan=values.get("workout_plan"),
        gym_data=values.get("gym_data"),
        general_response=values.get("general_response"),
        final_report=values.get("final_report"),
        goal=values.get("goal"),
        success_criteria=values.get("success_criteria"),
        plan=values.get("plan"),
        completed_tasks=values.get("completed_tasks") or [],
        failed_tasks=values.get("failed_tasks") or [],
        action_history=values.get("action_history") or [],
        plan_version=values.get("plan_version") or 0,
        goal_completed=values.get("goal_completed") or False,
        final_status=values.get("final_status"),
        tool_results=values.get("tool_results") or {},
        replan_count=values.get("replan_count") or 0,
        evaluation=values.get("evaluation"),
        task_validation=values.get("task_validation") or {},
        constraints=values.get("constraints") or {},
        llm_calls=values.get("llm_calls") or 0,
        llm_tokens=values.get("llm_tokens") or 0,
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Clear the checkpointed runtime state for a session."""
    _get_session_values(session_id)  # 404 if it doesn't exist

    checkpointer = app_graph.checkpointer
    if checkpointer is not None:
        checkpointer.delete_thread(session_id)

    return {"status": "success", "message": f"Session '{session_id}' cleared."}
