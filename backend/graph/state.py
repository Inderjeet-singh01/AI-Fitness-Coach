import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from schemas.schemas import UserProfileData


class AgentState(TypedDict, total=False):
    """
    Runtime state for a single session, persisted across requests by the
    LangGraph checkpointer (thread_id == session_id). Only the channels a
    node returns are updated; everything else keeps its last checkpointed
    value, which is what lets `user_profile` survive across chat turns
    without being resent every time.
    """

    # --- Session / identity ---
    session_id: Optional[str]
    user_profile: UserProfileData
    user_query: str

    # --- Runtime conversation memory ---
    # Accumulates across graph runs for the same thread_id via the reducer,
    # replacing the old manual SessionMemoryStore.
    messages: Annotated[List[Dict[str, str]], operator.add]

    # --- Tool routing (informational only; derived from the plan) ---
    selected_tools: List[str]

    # --- Latest known tool data (session context) ---
    # Tools read these (e.g. diet reads macro_data), so they intentionally
    # survive across turns; the response for a turn is built only from that
    # turn's `tool_results`, never from these directly.
    bmi_data: Optional[Dict[str, Any]]
    water_data: Optional[Dict[str, Any]]
    macro_data: Optional[Dict[str, Any]]

    diet_plan: Optional[str]
    workout_plan: Optional[str]
    gym_data: Optional[str]

    # General Conversational Output
    general_response: Optional[str]

    retry_count: int
    current_errors: List[str]
    final_report: Optional[str]

    # --- Plan + ReAct execution loop (reset by the planner every turn) ---
    goal: Optional[str]
    success_criteria: Optional[List[str]]
    plan: Optional[List[Dict[str, Any]]]
    plan_version: int
    # Validation errors from the planner's LLM output (a non-empty list
    # means the turn fell back to a general-only plan).
    plan_errors: List[str]
    current_task: Optional[Dict[str, Any]]
    completed_tasks: List[Dict[str, Any]]
    failed_tasks: List[Dict[str, Any]]
    action_history: List[Dict[str, Any]]
    # Current turn's results, keyed by action.
    tool_results: Dict[str, Any]
    agent_results: Dict[str, Any]
    # What the last executed task produced; the executor decides from it.
    last_observation: Optional[Dict[str, Any]]
    execution_steps: int
    next_action: Optional[str]

    # --- Evaluator / replanner ---
    # evaluation["decision"] is continue | replan | complete.
    evaluation: Optional[Dict[str, Any]]
    # success | needs_input | incomplete | error, set when the turn completes.
    final_status: Optional[str]
    goal_completed: bool
    replan_required: bool
    replan_reason: Optional[str]
    replan_count: int
    # Short, targeted summary of the latest evaluation's issues, handed to
    # the relevant generative worker (diet/workout) on a replan so it can
    # correct the specific problem instead of regenerating blind.
    replan_feedback: Optional[str]

    # --- Task-level validation (reset by the planner every turn) ---
    # action -> {"status": pending|validated|unknown|failed|unresolved,
    #            "task_id", "attempts", "issues", "codes", "history": [...]}
    task_validation: Dict[str, Dict[str, Any]]
    # action -> {"result", "validation", "task_id"}: the best result produced
    # this turn. A later failed/empty attempt never replaces a better one.
    best_results: Dict[str, Dict[str, Any]]
    # Explicit, checkable constraints extracted from the current message
    # (diet_type, cuisine, budget, daily_cost_required).
    constraints: Dict[str, Any]
    # Why the executor last handed off to the evaluator.
    handoff_reason: Optional[str]
    # Set when the turn must stop (rate limit / LLM budget); no further
    # planning, replanning or generation happens after it.
    turn_halt: Optional[Dict[str, Any]]
    # Per-turn LLM accounting (see models/llm.py).
    llm_calls: int
    llm_tokens: int
