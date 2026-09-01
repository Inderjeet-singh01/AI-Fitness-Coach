import json
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from graph.state import AgentState
from graph.workflow import app_graph
from memory.session_memory import SessionMemoryStore
from schemas.schemas import FitnessBotResponse, UserProfile

router = APIRouter()


def build_initial_state(profile: UserProfile, session_id: str) -> AgentState:
    return {
        "user_profile": profile,
        "session_id": session_id,
        "user_query": profile.query,
        "chat_history": SessionMemoryStore.get_history(session_id),
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
    }


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/generate-plan", response_model=FitnessBotResponse)
async def generate_fitness_plan(profile: UserProfile):
    session_id = profile.session_id or str(uuid.uuid4())
    initial_state = build_initial_state(profile, session_id)

    try:
        final_output = app_graph.invoke(initial_state)

        if not final_output.get("final_report"):
            raise HTTPException(status_code=500, detail="Engine failed to consolidate the final report.")

        SessionMemoryStore.append_message(session_id, "user", profile.query)
        SessionMemoryStore.append_message(session_id, "assistant", final_output["final_report"])

        return FitnessBotResponse(
            status="success",
            session_id=session_id,
            bmi_data=final_output.get("bmi_data"),
            water_data=final_output.get("water_data"),
            macro_data=final_output.get("macro_data"),
            final_report=final_output["final_report"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected architectural failure occurred: {str(e)}")


@router.post("/generate-plan/stream")
async def stream_fitness_plan(profile: UserProfile):
    """Stream LLM output as Server-Sent Events while the LangGraph workflow runs."""
    session_id = profile.session_id or str(uuid.uuid4())
    initial_state = build_initial_state(profile, session_id)

    async def event_generator() -> AsyncIterator[str]:
        try:
            yield sse("start", {"session_id": session_id})

            final_output = None
            current_node = None

            async for event in app_graph.astream_events(initial_state, version="v2"):
                event_type = event.get("event")
                metadata = event.get("metadata") or {}
                node = metadata.get("langgraph_node")

                if node and node != current_node:
                    current_node = node
                    if node in {"general_worker", "diet_worker", "workout_worker", "gym_worker"}:
                        yield sse("stage", {"node": node})

                # Stream only user-facing worker tokens. Planner and supervisor
                # output is intentionally hidden because it is internal control data.
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

            SessionMemoryStore.append_message(session_id, "user", profile.query)
            SessionMemoryStore.append_message(session_id, "assistant", final_output["final_report"])

            yield sse("done", {
                "status": "success",
                "session_id": session_id,
                "bmi_data": final_output.get("bmi_data"),
                "water_data": final_output.get("water_data"),
                "macro_data": final_output.get("macro_data"),
                "final_report": final_output["final_report"],
            })

        except Exception as e:
            detail = str(e)
            if "rate_limit" in detail.lower() or "tokens per minute" in detail.lower() or "error code: 429" in detail.lower():
                detail = "The coach is temporarily busy because the AI token limit was reached. Please try again in a few seconds."
            yield sse("error", {"detail": detail})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/clear-session/{session_id}")
async def clear_session_memory(session_id: str):
    try:
        SessionMemoryStore.clear_session(session_id)
        return {"status": "success", "message": f"Session memory cleared for session_id: {session_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear session memory: {str(e)}")
