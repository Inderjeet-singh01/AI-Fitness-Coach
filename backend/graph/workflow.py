from typing import Dict, Optional, Tuple

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END, START
from graph.state import AgentState
from agents.common import summarize_result
from config.settings import settings
from models.llm import TurnHalted, calls_in_current_node, last_finish_reason, llm_meter

# Import dynamic tools
from tools.bmi_tool import BMICalculatorTool
from tools.water_tool import WaterCalculatorTool
from tools.macro_tool import MacroCalculatorTool
from tools.diet_generator import DietGeneratorTool
from tools.workout_generator import WorkoutGeneratorTool
from tools.gym_finder import GymFinderTool
from tools.general_tool import GeneralFitnessTool
from tools.registry import get_node_map, get_state_key_map, get_type_map

# Import Agents
from agents.planner import PlannerAgent
from agents.executor import ExecutorAgent
from agents.evaluator import EvaluatorAgent
from agents.replanner import ReplannerAgent
from agents.aggregator import AggregatorAgent


# Registry-driven: action name -> graph node name. Adding/removing a
# capability only requires updating tools/registry.py.
NODE_BY_ACTION: Dict[str, str] = get_node_map()
STATE_KEY_BY_ACTION: Dict[str, str] = get_state_key_map()
TYPE_BY_ACTION: Dict[str, str] = get_type_map()

# Registry-driven: action name -> the function that actually executes it.
# Each of these is the same deterministic/LLM tool logic from Step 1,
# untouched; only how they're wired into the graph has changed.
RUN_FN_BY_ACTION = {
    "bmi": BMICalculatorTool.calculate,
    "water": WaterCalculatorTool.calculate,
    "macros": MacroCalculatorTool.calculate,
    "diet": DietGeneratorTool.generate_diet,
    "workout": WorkoutGeneratorTool.generate_workout,
    "gym": GymFinderTool.find_gyms,
    "general": GeneralFitnessTool.respond,
}


def _plan_with_status(plan: list, task_id: Optional[str], status: str, **extra) -> list:
    return [
        {**task, "status": status, **extra} if task.get("id") == task_id else task
        for task in plan
    ]


def _output_failure(action: str, result: dict) -> Optional[Tuple[str, str]]:
    """Reject output that must never be treated as a completed result."""
    value = result.get(STATE_KEY_BY_ACTION.get(action, ""))
    if value is None or (isinstance(value, str) and not value.strip()):
        return "output.empty", f"{action} returned no content"
    if calls_in_current_node() and last_finish_reason() == "length":
        return "output.truncated", f"{action} output was cut off at the output token limit"
    return None


def _run_task(action: str, run_fn, state: AgentState) -> dict:
    """
    ACT -> OBSERVE -> UPDATE STATE for one planned task. The result is
    recorded as this turn's result (tool_results), the task status is
    updated, and `last_observation` tells the executor what just happened
    so its next decision can depend on it. Control then returns to the
    executor node.

    Empty or truncated output is a task failure, never a completed result.
    A rate limit / exhausted LLM budget is not a task failure: it halts the
    turn so no further planning or generation is attempted.
    """
    current_task = state.get("current_task") or {}
    task_id = current_task.get("id")
    plan = state.get("plan") or []
    action_history = list(state.get("action_history") or [])

    # A retried task carries its own targeted instruction (what failed last
    # time); workers read it through the existing replan_feedback channel.
    feedback = current_task.get("instruction") or None

    failure: Optional[Tuple[str, str]] = None
    try:
        result = run_fn({**state, "replan_feedback": feedback}) or {}
        failure = _output_failure(action, result)
    except TurnHalted as exc:
        action_history.append({"task_id": task_id, "action": action, "event": "halted", "reason": exc.kind})
        return {
            "plan": _plan_with_status(plan, task_id, "halted", error=exc.kind),
            "action_history": action_history,
            "current_task": None,
            "turn_halt": {"kind": exc.kind, "detail": str(exc)[:300], "action": action},
            "last_observation": {"task_id": task_id, "action": action, "status": "halted", "error": exc.kind},
        }
    except Exception as exc:
        failure = ("error", f"{type(exc).__name__}: {exc}")

    if failure:
        code, message = failure
        failed_tasks = list(state.get("failed_tasks") or [])
        failed_tasks.append({**current_task, "status": "failed", "error": message, "failure_code": code})
        action_history.append({
            "task_id": task_id, "action": action, "event": "failed", "error": message, "code": code,
        })
        current_errors = list(state.get("current_errors") or [])
        current_errors.append(f"{action} failed: {message}")

        return {
            "plan": _plan_with_status(plan, task_id, "failed", error=message, failure_code=code),
            "failed_tasks": failed_tasks,
            "action_history": action_history,
            "current_errors": current_errors,
            "current_task": None,
            "last_observation": {"task_id": task_id, "action": action, "status": "failed", "error": message[:300]},
        }

    completed_tasks = list(state.get("completed_tasks") or [])
    completed_tasks.append({**current_task, "status": "completed"})
    action_history.append({"task_id": task_id, "action": action, "event": "completed"})

    tool_results = dict(state.get("tool_results") or {})
    tool_results[action] = result

    # Deterministic tool values feed later tools (e.g. macros -> diet) right
    # away; generative outputs reach the session channels only through
    # best_results once evaluated, so an unvalidated attempt never replaces
    # a better earlier one.
    session_values = result if TYPE_BY_ACTION.get(action) == "tool" else {}

    return {
        **session_values,
        "plan": _plan_with_status(plan, task_id, "completed"),
        "completed_tasks": completed_tasks,
        "action_history": action_history,
        "tool_results": tool_results,
        "current_task": None,
        "last_observation": {
            "task_id": task_id, "action": action, "status": "completed",
            "summary": summarize_result(result, 200),
        },
    }


def _metered(fn, reset: bool = False):
    """Run a node under the per-turn LLM meter and persist the counters."""
    def _node(state: AgentState) -> dict:
        with llm_meter(state, reset=reset) as meter:
            update = fn(state)
        return {**update, **meter.state_update()}

    return _node


def _make_worker_node(action: str):
    def _node(state: AgentState) -> dict:
        return _run_task(action, RUN_FN_BY_ACTION[action], state)

    return _metered(_node)


# --- Node Wrappers ---
# The planner starts a new turn, so it also resets the LLM counters.
planner_node = _metered(lambda state: PlannerAgent.plan_execution(state), reset=True)
executor_node = _metered(lambda state: ExecutorAgent.decide_next(state))
evaluator_node = _metered(lambda state: EvaluatorAgent.evaluate(state))
replanner_node = _metered(lambda state: ReplannerAgent.replan(state))
def aggregator_node(state: AgentState): return AggregatorAgent.compile_report(state)


def route_from_executor(state: AgentState) -> str:
    """
    Run whatever action the executor just decided on, or hand off to the
    evaluator once it reports the plan is exhausted (or the safety cap was
    hit) so goal completion - not just plan completion - gets checked.
    """
    next_action = state.get("next_action")
    return NODE_BY_ACTION.get(next_action, "evaluator")


def route_from_evaluator(state: AgentState) -> str:
    """
    The evaluator's decision controls the loop: continue executing the
    current plan, replan, or complete. needs_input / incomplete / error all
    complete through the aggregator, which never presents them as success.
    """
    decision = (state.get("evaluation") or {}).get("decision")
    return {"continue": "executor", "replan": "replanner"}.get(decision, "aggregator")


def run_config(session_id: str) -> dict:
    """LangGraph run config: session_id doubles as the checkpoint thread_id.

    recursion_limit is sized from the loop limits (each execution step is an
    executor + worker superstep, each generated task may add an evaluator +
    executor hop for its own validation, each replan adds evaluator +
    replanner) so MAX_EXECUTION_STEPS / MAX_REPLANS, not LangGraph's
    default of 25, are what stop a long turn.
    """
    return {
        "configurable": {"thread_id": session_id},
        "recursion_limit": 6 * settings.MAX_EXECUTION_STEPS + 4 * (settings.MAX_REPLANS + 1) + 10,
    }


# --- Workflow Graph Assembly ---
#
#   START -> planner -> executor -> <worker> -> executor -> ... -> evaluator
#                          ^  └──────────────────────┘                |
#                          |                               continue ──┤ (back to executor)
#                          └──────────── replanner <────── replan ────┤
#                                                          complete ──┴-> aggregator -> END
#
# `executor` is the ReAct decision point: decide -> act (worker) -> observe/
# update state (inside the worker node) -> decide again. When it hands off,
# `evaluator` checks *goal* completion (not just plan completion) and
# decides continue / replan / complete.
workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("executor", executor_node)
for _action, _node_name in NODE_BY_ACTION.items():
    workflow.add_node(_node_name, _make_worker_node(_action))
workflow.add_node("evaluator", evaluator_node)
workflow.add_node("replanner", replanner_node)
workflow.add_node("aggregator", aggregator_node)

workflow.add_edge(START, "planner")
workflow.add_edge("planner", "executor")

workflow.add_conditional_edges(
    "executor",
    route_from_executor,
    {**{node_name: node_name for node_name in NODE_BY_ACTION.values()}, "evaluator": "evaluator"},
)

for _node_name in NODE_BY_ACTION.values():
    workflow.add_edge(_node_name, "executor")

workflow.add_conditional_edges(
    "evaluator",
    route_from_evaluator,
    {"executor": "executor", "replanner": "replanner", "aggregator": "aggregator"},
)
workflow.add_edge("replanner", "executor")

workflow.add_edge("aggregator", END)

# Runtime state (conversation + profile + tool outputs) is checkpointed
# in-memory per thread_id (== session_id), replacing the old manual
# SessionMemoryStore. No persistent/cross-session storage is added.
checkpointer = MemorySaver()
app_graph = workflow.compile(checkpointer=checkpointer)
