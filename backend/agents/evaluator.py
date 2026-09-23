import re
from typing import Any, Dict, List, Optional, Set, Tuple

from langchain_core.prompts import ChatPromptTemplate

from agents.common import (
    dependency_met,
    extract_json_object,
    needs_validation,
    update_best,
    validation_for,
)
from agents.constraints import describe_constraints, extract_daily_cost, find_diet_violations
from config.settings import settings
from graph.state import AgentState
from models.llm import TurnHalted, call_llm, get_llm
from tools.registry import get_state_key_map

'''
                START
                  │
                  ▼
      Turn halted (rate limit / LLM budget)? → finalize, no LLM call
                  │
                  ▼
      Record execution failures (error / empty / truncated output)
                  │
                  ▼
      For each task attempt NOT yet evaluated (each one on its own):
        deterministic checks (pure Python)      → FAIL, or
        diet/workout: one LLM judge call         → PASS | FAIL | UNKNOWN
        everything else                          → PASS
      and keep the best result per task (validated > unknown > failed)
                  │
                  ▼
      Retry policy per task: a failed task may be retried up to
      MAX_TASK_RETRIES times, and never again once the same failure
      code repeats → otherwise "unresolved" (best result is kept)
                  │
                  ▼
      Decision:
      - runnable work still pending           -> continue (fix failures later)
      - retryable failures, within limits     -> replan (only those tasks)
      - unresolved task blocks dependents     -> one structural replan
      - otherwise                             -> complete with an honest status
                  │
                  ▼
                 END

Previously validated tasks are never evaluated again in the same turn.
UNKNOWN (the judge returned nothing usable) never triggers regeneration.
'''

# Outputs whose fit with the user's request needs judgment. Numbers, costs and
# forbidden ingredients are checked in Python first; gym output is grounded in
# fetched place data and general replies are conversational, so both are
# validated deterministically (non-empty output is enforced by the worker).
SEMANTIC_ACTIONS: Set[str] = {"diet", "workout"}

SEMANTIC_CHECKS: Dict[str, List[Tuple[str, str]]] = {
    "diet": [
        ("goal", "The plan fits the user's stated goal."),
        ("constraints", "It respects preferences/constraints stated in the user message (allergies, dislikes, schedule)."),
        ("safety", "It contains no unsafe or medically risky advice."),
    ],
    "workout": [
        ("goal", "The workout fits the user's stated goal."),
        ("constraints", "It respects constraints stated in the user message (injuries, equipment, available time)."),
        ("structure", "Each day lists concrete exercises with sets/reps or duration."),
        ("safety", "It contains no unsafe or medically risky advice."),
    ],
}

FIELD_LABELS: Dict[str, str] = {
    "weight_kg": "weight (kg)",
    "height_cm": "height (cm)",
    "age": "age",
    "gender": "gender",
    "activity_level": "activity level (sedentary/lightly_active/moderately_active/very_active)",
    "location": "location (city/area)",
}

# Matches a "Daily Totals" line the diet generator is prompted to always
# emit, e.g.: "**Daily Totals:** ~1800 kcal | Protein: 150g | Carbs: 180g | Fats: 55g"
_DIET_TOTALS_RE = re.compile(
    r"daily\s*totals?[:\*\s]*~?\s*([\d,.]+)\s*kcal[^\d]*protein[:\s]*([\d.]+)\s*g",
    re.IGNORECASE,
)

# How far a generated result may drift from its deterministic target before
# it's treated as a real mismatch rather than normal rounding/estimation.
_TOLERANCE = 0.15

STATE_KEY_BY_ACTION = get_state_key_map()


def _turn_result(state: AgentState, action: str, key: str) -> Any:
    """A result produced by THIS turn's plan (never a previous turn's)."""
    return ((state.get("tool_results") or {}).get(action) or {}).get(key)


def _is_finite_positive(value: Any) -> bool:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf")) and number > 0


def _extract_diet_totals(diet_plan: Optional[str]) -> Optional[Dict[str, float]]:
    if not diet_plan:
        return None
    match = _DIET_TOTALS_RE.search(diet_plan)
    if not match:
        return None
    try:
        return {"calories": float(match.group(1).replace(",", "")), "protein_g": float(match.group(2))}
    except ValueError:
        return None


def _deterministic_issues(state: AgentState, action: str) -> List[Tuple[str, str]]:
    """Pure-Python checks for one task's result. Returns [(code, issue)]."""
    issues: List[Tuple[str, str]] = []

    if action == "bmi":
        bmi_data = _turn_result(state, "bmi", "bmi_data") or {}
        if not (_is_finite_positive(bmi_data.get("bmi_value")) and _is_finite_positive(bmi_data.get("bmr"))):
            issues.append(("bmi.invalid", "Computed BMI/BMR value is invalid."))

    elif action == "macros":
        macro_data = _turn_result(state, "macros", "macro_data") or {}
        if not _is_finite_positive(macro_data.get("daily_calories_target")):
            issues.append(("macros.invalid", "Computed calorie target is invalid."))

    elif action == "water":
        water_data = _turn_result(state, "water", "water_data") or {}
        if not _is_finite_positive(water_data.get("water_intake_liters")):
            issues.append(("water.invalid", "Computed water target is invalid."))

    elif action == "diet":
        diet_plan = _turn_result(state, "diet", "diet_plan") or ""
        constraints = state.get("constraints") or {}
        totals = _extract_diet_totals(diet_plan)
        if not totals:
            issues.append(("diet.missing_totals",
                           "The diet plan is missing the required '**Daily Totals:**' line with calories and protein."))

        # Only THIS turn's macro targets are used; an earlier turn's numbers
        # may belong to a different goal.
        target = _turn_result(state, "macros", "macro_data")
        if totals and target:
            target_calories = target.get("daily_calories_target")
            if target_calories and abs(totals["calories"] - target_calories) / max(target_calories, 1) > _TOLERANCE:
                issues.append(("diet.calories_off",
                               f"Diet calories ({totals['calories']:.0f} kcal) are more than {int(_TOLERANCE * 100)}% "
                               f"away from the target ({target_calories:.0f} kcal)."))
            target_protein = target.get("protein_g")
            if target_protein:
                minimum = target.get("protein_min_g") or target_protein * (1 - _TOLERANCE)
                maximum = target_protein * (1 + _TOLERANCE)
                if totals["protein_g"] < minimum:
                    issues.append(("diet.protein_low",
                                   f"Diet protein ({totals['protein_g']:.0f}g) is below the minimum ({minimum:.0f}g); "
                                   f"target range is {minimum:.0f}-{target_protein:.0f}g."))
                elif totals["protein_g"] > maximum:
                    issues.append(("diet.protein_high",
                                   f"Diet protein ({totals['protein_g']:.0f}g) is above the target range "
                                   f"(up to {maximum:.0f}g)."))

        diet_type = constraints.get("diet_type")
        violations = find_diet_violations(diet_plan, diet_type)
        if violations:
            issues.append((f"diet.not_{diet_type}",
                           f"The diet includes items not allowed for a {diet_type} diet: {', '.join(violations)}."))

        if constraints.get("daily_cost_required") and extract_daily_cost(diet_plan) is None:
            issues.append(("diet.missing_daily_cost",
                           "The user asked for a low-budget diet, so the plan must state "
                           "'**Estimated Daily Cost:** ~<amount>'."))

    return issues


def _semantic_check(state: AgentState, task: Dict[str, Any]) -> Dict[str, Any]:
    """One LLM judge call for ONE generated task. Returns
    {"verdict": pass|fail|unknown, "issues": [...], "failed_checks": [...]}.

    Empty, malformed or unreadable judge output is UNKNOWN, never FAIL: a
    judge problem must not cause valid work to be regenerated."""
    action = task["action"]
    checks = list(SEMANTIC_CHECKS.get(action, []))
    constraints = state.get("constraints") or {}
    if action == "diet" and constraints.get("cuisine"):
        checks.append(("cuisine", f"Most meals are recognisable {constraints['cuisine']} dishes."))
    check_ids = [check_id for check_id, _ in checks]

    llm = get_llm(temperature=0.0, purpose="router")
    prompt = ChatPromptTemplate.from_messages([
        ("system", (
            "You are the evaluation stage of a fitness planning agent.\n\n"
            "Judge ONE generated {kind} against this fixed checklist:\n{checklist}\n\n"
            "Rules:\n"
            "- Fail a check only for a concrete, visible violation in the output.\n"
            "- Do not fail for style, length, or detail the user did not ask for.\n"
            "- Numbers, calorie/protein totals, costs and forbidden ingredients were already verified in code; do not re-judge them.\n\n"
            "Return ONLY a JSON object with this exact shape:\n"
            '{{"status": "pass" or "fail", "failed_checks": ["<check id>"], "issues": ["<one short sentence per failed check>"]}}\n'
            "Do not return markdown, explanations, or code fences."
        )),
        ("user", (
            "User Message: {query}\n"
            "Goal: {goal}\n"
            "Explicit Constraints:\n{constraints}\n\n"
            "{kind} Output:\n{output}"
        )),
    ])

    response = call_llm(prompt | llm, {
        "kind": action,
        "checklist": "\n".join(f"- {check_id}: {text}" for check_id, text in checks),
        "query": state.get("user_query") or "",
        "goal": state.get("goal") or "",
        "constraints": describe_constraints(constraints),
        "output": _turn_result(state, action, STATE_KEY_BY_ACTION[action]) or "",
    })

    parsed = extract_json_object((getattr(response, "content", "") or "").strip()) or {}
    status = str(parsed.get("status", "")).strip().lower()
    issues = [str(item) for item in (parsed.get("issues") or []) if str(item).strip()]
    failed = [c for c in (parsed.get("failed_checks") or []) if c in check_ids]

    if status == "pass":
        return {"verdict": "pass", "issues": [], "failed_checks": []}
    if status == "fail":
        return {
            "verdict": "fail",
            "issues": issues or [f"The {action} output did not meet the checklist."],
            "failed_checks": failed or ["general"],
        }
    return {"verdict": "unknown", "issues": ["The evaluator's answer could not be read, so this result was not verified."],
            "failed_checks": []}


def _record(task_validation: Dict[str, Dict[str, Any]], task: Dict[str, Any], status: str,
            issues: List[str], codes: List[str]) -> Dict[str, Any]:
    previous = task_validation.get(task["action"]) or {}
    record = {
        "status": status,
        "task_id": task["id"],
        "attempts": (previous.get("attempts") or 0) + 1,
        "issues": issues,
        "codes": sorted(set(codes)),
        "history": list(previous.get("history") or []) + [
            {"task_id": task["id"], "status": status, "codes": sorted(set(codes)), "issues": issues[:3]}
        ],
    }
    task_validation[task["action"]] = record
    return record


def _stop_reason(record: Dict[str, Any]) -> Optional[str]:
    """Why a failed task may not be retried again, or None if it may."""
    if (record.get("attempts") or 0) - 1 >= settings.MAX_TASK_RETRIES:
        return "retry_limit"
    earlier_codes = {
        code
        for entry in (record.get("history") or [])[:-1]
        if entry.get("status") in ("failed", "unresolved")
        for code in entry.get("codes") or []
    }
    if earlier_codes & set(record.get("codes") or []):
        return "repeated"
    return None


class EvaluatorAgent:
    """
    Task-level evaluation for the agentic loop: validates each task attempt
    once, keeps the best result per task, applies the per-task retry policy
    and decides continue / replan / complete. Deterministic Python checks run
    first; an LLM judge is only called for a newly generated diet/workout.
    """

    @staticmethod
    def evaluate(state: AgentState) -> Dict[str, Any]:
        plan = [dict(task) for task in (state.get("plan") or [])]
        action_history = list(state.get("action_history") or [])
        task_validation = {k: dict(v) for k, v in (state.get("task_validation") or {}).items()}
        best_results = dict(state.get("best_results") or {})
        tool_results = state.get("tool_results") or {}
        halt = state.get("turn_halt")
        replan_count = state.get("replan_count") or 0
        steps = state.get("execution_steps") or 0
        steps_exhausted = steps >= settings.MAX_EXECUTION_STEPS
        extra: Dict[str, Any] = {}

        # --- Record execution failures (error / empty / truncated output) ---
        for task in plan:
            if task.get("status") == "failed" and validation_for(task, task_validation) is None:
                _record(task_validation, task, "failed",
                        [f"'{task['action']}' failed: {task.get('error', 'unknown error')}"],
                        [task.get("failure_code") or "error"])

        # --- Evaluate each new attempt on its own ---
        for task in plan:
            if not needs_validation(task, task_validation):
                continue
            action = task["action"]
            if halt:
                verdict = {"verdict": "unknown", "failed_checks": [],
                           "issues": ["Not verified: the turn stopped before evaluation."]}
            else:
                deterministic = _deterministic_issues(state, action)
                if deterministic:
                    verdict = {"verdict": "fail", "failed_checks": [c for c, _ in deterministic],
                               "issues": [i for _, i in deterministic]}
                elif action in SEMANTIC_ACTIONS:
                    try:
                        verdict = _semantic_check(state, task)
                        verdict = {**verdict, "failed_checks": [f"semantic.{c}" for c in verdict["failed_checks"]]}
                    except TurnHalted as exc:
                        halt = {"kind": exc.kind, "detail": str(exc)[:300], "action": "evaluator"}
                        extra["turn_halt"] = halt
                        verdict = {"verdict": "unknown", "failed_checks": [],
                                   "issues": ["Not verified: the turn stopped before evaluation."]}
                else:
                    verdict = {"verdict": "pass", "failed_checks": [], "issues": []}

            status = {"pass": "validated", "fail": "failed"}.get(verdict["verdict"], "unknown")
            _record(task_validation, task, status, verdict["issues"], verdict["failed_checks"])
            stored = update_best(best_results, action, task["id"], tool_results.get(action), status)
            action_history.append({
                "event": "task_evaluated", "task_id": task["id"], "action": action, "validation": status,
                "codes": verdict["failed_checks"], "kept_as_best": stored,
            })

        # --- Retry policy ---
        for action, record in task_validation.items():
            if record["status"] == "failed":
                reason = _stop_reason(record)
                if reason:
                    record["status"] = "unresolved"
                    record["stop_reason"] = reason

        # The session-level channels always hold the best result, so a failed
        # retry can never erase an earlier valid one.
        session_values = {
            STATE_KEY_BY_ACTION[action]: (entry.get("result") or {}).get(STATE_KEY_BY_ACTION[action])
            for action, entry in best_results.items()
            if action in STATE_KEY_BY_ACTION and isinstance(entry.get("result"), dict)
        }
        base = {"task_validation": task_validation, "best_results": best_results, **session_values, **extra}

        def result(**kwargs) -> Dict[str, Any]:
            update = EvaluatorAgent._result(action_history, **kwargs)
            state_extra = {k: v for k, v in (kwargs.get("extra") or {}).items() if k != "replan_mode"}
            return {**base, **update, **state_extra}

        retryable = sorted(a for a, r in task_validation.items() if r["status"] == "failed")
        issues_for = lambda actions: [i for a in actions for i in task_validation[a].get("issues") or []]

        if halt:
            return EvaluatorAgent._complete_halted(plan, halt, result)

        by_id = {task["id"]: task for task in plan}
        runnable = [
            task for task in plan
            if task.get("status") == "pending"
            and all(dependency_met(by_id.get(dep), task_validation) for dep in (task.get("depends_on") or []))
        ]
        fix_now = (state.get("handoff_reason") or "").startswith("after_failure")

        # Independent work still to do: keep executing and fix failures after,
        # unless the executor explicitly chose to stop and fix now.
        if runnable and not steps_exhausted and not (retryable and fix_now):
            return result(decision="continue", status="in_progress", issues=[],
                          extra={"last_observation": None})

        within_limits = replan_count < settings.MAX_REPLANS and not steps_exhausted
        if retryable:
            if within_limits:
                return result(decision="replan", status="fail", issues=issues_for(retryable),
                              failing_actions=set(retryable),
                              extra={"replan_reason": "; ".join(issues_for(retryable))[:500]})
            for action in retryable:
                task_validation[action]["status"] = "unresolved"
                task_validation[action]["stop_reason"] = "replan_limit" if replan_count >= settings.MAX_REPLANS else "step_limit"

        # An unresolved task blocks tasks that depend on it: the plan structure
        # itself must change, which is the one case the LLM replanner handles.
        unresolved = sorted(a for a, r in task_validation.items() if r["status"] == "unresolved")
        blocked = [
            task["action"] for task in plan
            if task.get("status") == "skipped"
            and any((by_id.get(dep) or {}).get("action") in unresolved for dep in task.get("depends_on") or [])
        ]
        structural_done = any(e.get("event") == "replanned" and e.get("mode") == "structural" for e in action_history)
        if blocked and within_limits and not structural_done:
            return result(decision="replan", status="fail", issues=issues_for(unresolved),
                          failing_actions=set(blocked),
                          extra={"replan_reason": f"{', '.join(unresolved)} could not be completed and blocks "
                                                  f"{', '.join(blocked)}", "replan_mode": "structural"})

        return EvaluatorAgent._complete(state, plan, task_validation, steps_exhausted, result)

    @staticmethod
    def _complete_halted(plan, halt, result) -> Dict[str, Any]:
        kind = halt.get("kind") or "rate_limited"
        done = [t["action"] for t in plan if t.get("status") == "completed"]
        not_done = [t["action"] for t in plan if t.get("status") != "completed"]
        if kind == "budget_exhausted":
            reason = "I reached this request's AI usage limit, so I stopped here instead of spending more of your quota."
        else:
            reason = "The AI service's rate limit was reached, so I stopped here instead of retrying further."
        message = reason
        if done:
            message += " Everything shown below was completed."
        if not_done:
            message += f" Not finished: {', '.join(not_done)}. Please try again in a minute."
        return result(decision="complete", status=kind, issues=[halt.get("detail") or kind], user_message=message)

    @staticmethod
    def _complete(state, plan, task_validation, steps_exhausted, result) -> Dict[str, Any]:
        issues: List[str] = []
        messages: List[str] = []
        status = "success"

        unresolved = {a: r for a, r in task_validation.items() if r["status"] == "unresolved"}
        if unresolved:
            status = "incomplete"
            parts = []
            for action, record in unresolved.items():
                issues.extend(record.get("issues") or [])
                why = {
                    "repeated": "the same problem repeated",
                    "retry_limit": "the retry limit was reached",
                    "replan_limit": "the replanning limit was reached",
                    "step_limit": "the execution step limit was reached",
                }.get(record.get("stop_reason"), "it kept failing")
                parts.append(f"{action} ({why}: {'; '.join(record.get('issues') or [])})")
            messages.append("I couldn't fully meet every requirement for " + "; ".join(parts)
                            + ". Where I produced a version, the best one is shown - please review it.")

        pending = [t for t in plan if t.get("status") in ("pending", "running")]
        if pending:
            status = "incomplete"
            issues.append("Execution stopped before all tasks ran: " + ", ".join(t["action"] for t in pending))
            messages.append("I hit the execution step limit before finishing everything you asked for."
                            if steps_exhausted else "I couldn't finish every part of this request.")

        needs_input = {t["action"]: t.get("missing_fields") or [] for t in plan if t.get("status") == "needs_input"}
        if needs_input:
            if status == "success":
                status = "needs_input"
            fields = sorted({field for missing in needs_input.values() for field in missing})
            issues.extend(f"'{action}' needs: {missing}" for action, missing in needs_input.items())
            messages.append("I need a bit more information before I can do that: "
                            + ", ".join(FIELD_LABELS.get(f, f) for f in fields)
                            + ". Please add it to your profile and ask again.")

        if state.get("plan_errors"):
            status = "incomplete"
            issues.append("Planner output was invalid: " + " ".join(state["plan_errors"]))
            messages.append("I couldn't build a reliable plan for this request, so this is only a general answer.")

        skipped = [t["action"] for t in plan if t.get("status") == "skipped"
                   and t["action"] not in unresolved]
        if skipped:
            status = "incomplete"
            issues.append("Skipped because a required step failed: " + ", ".join(skipped))
            messages.append(f"I couldn't do {', '.join(skipped)} because a step it depends on failed.")

        unknown = [a for a, r in task_validation.items() if r["status"] == "unknown"]
        if unknown:
            if status == "success":
                status = "needs_review"
            issues.extend(i for a in unknown for i in task_validation[a].get("issues") or [])
            messages.append(f"I couldn't automatically verify the {', '.join(unknown)} result"
                            f"{'s' if len(unknown) > 1 else ''}, so please review "
                            f"{'them' if len(unknown) > 1 else 'it'}.")

        return result(decision="complete", status=status, issues=issues,
                      user_message=" ".join(messages) if status != "success" else None)

    @staticmethod
    def _result(
        action_history: List[Dict[str, Any]],
        decision: str,
        status: str,
        issues: List[str],
        failing_actions: Optional[Set[str]] = None,
        user_message: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        goal_completed = decision == "complete" and status == "success"
        evaluation: Dict[str, Any] = {
            "decision": decision,
            "status": status,
            "goal_completed": goal_completed,
            "replan_required": decision == "replan",
            "issues": issues,
            "failing_actions": sorted(failing_actions or []),
        }
        if user_message:
            evaluation["user_message"] = user_message
        if extra and extra.get("replan_mode"):
            evaluation["replan_mode"] = extra["replan_mode"]

        action_history = action_history + [{"event": "evaluated", "decision": decision, "status": status}]
        update: Dict[str, Any] = {
            "evaluation": evaluation,
            "goal_completed": goal_completed,
            "replan_required": decision == "replan",
            "action_history": action_history,
        }
        if decision == "complete":
            update["final_status"] = status
        return update
