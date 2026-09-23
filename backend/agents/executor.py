import json
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from agents.common import (
    dependency_blocked,
    dependency_met,
    extract_json_object,
    missing_profile_fields,
    needs_validation,
    summarize_result,
)
from config.settings import settings
from graph.state import AgentState
from models.llm import TurnHalted, call_llm, get_llm
from tools.registry import get_requirements_map


REQUIREMENTS_BY_ACTION = get_requirements_map()

# Pseudo-action: stop executing and hand the current state to the evaluator.
EVALUATE = "evaluate"

'''
                START
                  │
                  ▼
      Turn halted (rate limit / LLM budget)? ──Yes──> evaluator (finalize)
                  │ No
                  ▼
      UPDATE: settle tasks the latest state already decides
      (dependency failed/blocked -> skipped,
       required profile field missing -> needs_input)
                  │
                  ▼
      A generated task just finished and is not yet evaluated?
                  │ Yes ──> evaluator (evaluates only that task, then continue)
                  ▼ No
      runnable = pending tasks whose dependencies completed (and did not
                 fail validation)
                  │
                  ▼
      None runnable / step cap reached? ──Yes──> evaluator
                  │ No
                  ▼
      DECIDE:
      - last observation failed      -> router LLM: run one of runnable, or evaluate
      - a deterministic tool runnable -> run it (no LLM; order can't change the result)
      - exactly one runnable          -> run it (no LLM)
      - several generative tasks      -> router LLM picks, given latest results
                  │
                  ▼
      ACT: route to that task's worker node, which executes, OBSERVES
      (last_observation + tool_results) and returns here to decide again.
'''


def _observation_lines(state: AgentState, plan: List[Dict[str, Any]]) -> str:
    results = state.get("tool_results") or {}
    lines = []
    for task in plan:
        if task["action"] in results and task.get("status") == "completed":
            lines.append(f"- {task['id']} {task['action']}: {summarize_result(results[task['action']], 200)}")
        elif task.get("status") == "failed":
            lines.append(f"- {task['id']} {task['action']}: FAILED ({task.get('error', 'unknown error')})")
    return "\n".join(lines) or "None yet."


def _llm_decide(state: AgentState, plan: List[Dict[str, Any]], options: List[str]) -> Optional[str]:
    """One cheap router call choosing the next step from `options`.
    Returns None on an invalid/unparseable answer so the caller can fall
    back deterministically."""
    llm = get_llm(temperature=0.0, purpose="router")
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are the execution controller of a fitness planning agent.\n"
            "Choose the single best next step using the latest results.\n"
            "- Pick a task id to run it next.\n"
            "- Pick 'evaluate' (only if offered) when the latest result shows the remaining "
            "tasks can no longer achieve the goal and the plan should be re-checked now.\n"
            "Return ONLY a JSON object: {{\"next\": \"<one of the options>\"}}. No explanations."
        )),
        ("user", (
            "User message: {query}\n"
            "Goal: {goal}\n"
            "Success criteria: {criteria}\n\n"
            "Plan:\n{plan}\n\n"
            "Latest observation: {observation}\n\n"
            "Results so far:\n{results}\n\n"
            "Options: {options}"
        )),
    ])
    observation = state.get("last_observation") or {}
    response = call_llm(prompt | llm, {
        "query": state.get("user_query") or "",
        "goal": state.get("goal") or "",
        "criteria": "; ".join(state.get("success_criteria") or []),
        "plan": json.dumps(
            [{k: t.get(k) for k in ("id", "action", "status", "depends_on")} for t in plan],
            ensure_ascii=False,
        ),
        "observation": json.dumps(observation, ensure_ascii=False) if observation else "None",
        "results": _observation_lines(state, plan),
        "options": ", ".join(options),
    })
    parsed = extract_json_object((response.content or "").strip()) or {}
    choice = parsed.get("next")
    return choice if choice in options else None


class ExecutorAgent:
    """
    The ReAct decision node: DECIDE -> ACT (worker) -> OBSERVE/UPDATE
    (worker writes last_observation/tool_results) -> DECIDE again.

    The next action is chosen from the *current* state each time, so it can
    change based on the latest result (e.g. stop and re-evaluate after a
    failure). `selected_tools` is informational only and never consulted.
    """

    @staticmethod
    def decide_next(state: AgentState) -> Dict[str, Any]:
        plan: List[Dict[str, Any]] = [dict(task) for task in (state.get("plan") or [])]
        action_history = list(state.get("action_history") or [])
        steps = state.get("execution_steps", 0)
        profile = state.get("user_profile")
        observation = state.get("last_observation") or {}
        task_validation = state.get("task_validation") or {}

        def handoff(reason: str, **extra: Any) -> Dict[str, Any]:
            action_history.append({"event": "handoff_to_evaluator", "reason": reason, "execution_steps": steps})
            return {
                "plan": plan,
                "current_task": None,
                "action_history": action_history,
                "next_action": EVALUATE,
                "handoff_reason": reason,
                **extra,
            }

        # A halted turn (rate limit / budget) does no more work.
        if state.get("turn_halt"):
            return handoff("turn_halted")

        # --- UPDATE: settle tasks whose outcome the state already determines ---
        by_id = {task["id"]: task for task in plan}
        changed = True
        while changed:
            changed = False
            for task in plan:
                if task.get("status") != "pending":
                    continue
                depends_on = task.get("depends_on") or []
                if any(dependency_blocked(by_id.get(dep), task_validation) for dep in depends_on):
                    task["status"] = "skipped"
                    event = {"task_id": task["id"], "action": task["action"], "event": "skipped_dependency_unmet"}
                else:
                    missing = missing_profile_fields(profile, REQUIREMENTS_BY_ACTION.get(task["action"], []))
                    if not missing:
                        continue
                    task["status"] = "needs_input"
                    task["missing_fields"] = missing
                    event = {"task_id": task["id"], "action": task["action"], "event": "needs_input", "missing": missing}
                action_history.append(event)
                changed = True

        # Evaluate each generated output on its own, as soon as it exists,
        # so later cycles never have to re-judge it.
        unevaluated = [
            task for task in plan
            if task.get("type") == "agent" and needs_validation(task, task_validation)
        ]
        if unevaluated:
            return handoff(f"validate_{unevaluated[0]['action']}")

        runnable = [
            task for task in plan
            if task.get("status") == "pending"
            and all(dependency_met(by_id.get(dep), task_validation) for dep in (task.get("depends_on") or []))
        ]

        if not runnable:
            return handoff("no_runnable_tasks")
        # Hard cap on tasks dispatched per turn, across the initial plan AND
        # any replans, so no plan/decision bug can loop forever.
        if steps >= settings.MAX_EXECUTION_STEPS:
            return handoff("max_execution_steps_reached")

        # --- DECIDE ---
        chosen: Optional[Dict[str, Any]] = None
        decided_by = "rule"
        last_failed = bool(observation) and observation.get("status") == "failed"
        tools = [task for task in runnable if task.get("type") == "tool"]

        try:
            if last_failed:
                # A real choice: keep going with independent work, or stop
                # and fix the failure now.
                options = [task["id"] for task in runnable] + [EVALUATE]
                choice = _llm_decide(state, plan, options)
                decided_by = "llm" if choice else "fallback"
                if choice in (None, EVALUATE):
                    return handoff(f"after_failure_of_{observation.get('action')}")
                chosen = next(task for task in runnable if task["id"] == choice)
            elif tools:
                chosen = tools[0]
            elif len(runnable) == 1:
                # Only one valid action: no LLM decision needed.
                chosen = runnable[0]
            else:
                options = [task["id"] for task in runnable]
                choice = _llm_decide(state, plan, options)
                decided_by = "llm" if choice else "fallback"
                chosen = next((task for task in runnable if task["id"] == choice), runnable[0])
        except TurnHalted as exc:
            return handoff("turn_halted", turn_halt={"kind": exc.kind, "detail": str(exc)[:300], "action": "executor"})

        # --- ACT (dispatched by the graph router) ---
        chosen["status"] = "running"
        action_history.append({
            "task_id": chosen["id"], "action": chosen["action"], "event": "decided", "by": decided_by,
        })
        return {
            "plan": plan,
            "current_task": chosen,
            "action_history": action_history,
            "execution_steps": steps + 1,
            "next_action": chosen["action"],
            "handoff_reason": None,
        }
