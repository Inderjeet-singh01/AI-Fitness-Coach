import json
from typing import Any, Dict, List, Set, Tuple

from langchain_core.prompts import ChatPromptTemplate

from agents.common import extract_json_object, summarize_result, tasks_from_llm, validate_plan
from graph.state import AgentState
from models.llm import TurnHalted, call_llm, get_llm
from tools.registry import get_all_tool_names, get_tools_metadata, get_type_map

'''
                START
                  │
                  ▼
      Evaluator asked for a replan. Which kind?
                  │
      ┌───────────┴────────────────────────────┐
      ▼ retry (common case, NO LLM)            ▼ structural (plan must change)
  Minimal corrective plan in Python:       An unresolved task blocks others.
  {"retry_tasks": [failed + stale deps],   LLM (router model) proposes new
   "preserve_tasks": [everything else]}    tasks around it: {"keep", "tasks"}
  Each retried task gets a targeted        -> validate -> one repair call ->
  instruction built from ITS failure       still invalid -> keep the plan as is
  codes (e.g. "answer was cut off -        (dependents stay skipped)
  keep it shorter").
      └───────────┬────────────────────────────┘
                  ▼
      Goal and success criteria are never rewritten. Validated results and
      best_results are preserved; only the retried tasks' current-attempt
      slot in tool_results is cleared. plan_version += 1, replan_count += 1
'''

# Targeted hints appended to a retried task's instruction, keyed by failure code.
_RETRY_HINTS: Dict[str, str] = {
    "output.truncated": "Your previous answer was cut off before the end. Keep the whole answer under about 350 words "
                        "and finish with the required final line(s).",
    "output.empty": "Your previous answer was empty. Answer directly and concisely.",
    "diet.missing_totals": "End with the exact '**Daily Totals:**' line.",
    "diet.protein_low": "Raise protein with affordable protein-dense foods that fit the stated diet type, "
                        "and restate the Daily Totals honestly.",
    "diet.missing_daily_cost": "End with '**Estimated Daily Cost:** ~<amount>' in the user's local currency.",
}


def _next_index(plan: List[Dict[str, Any]]) -> int:
    numbers = [int(task["id"][1:]) for task in plan if str(task.get("id", "")).startswith("t") and task["id"][1:].isdigit()]
    return (max(numbers) if numbers else 0) + 1


class ReplannerAgent:
    """
    Builds a corrective plan when the evaluator finds failed tasks:
    retries only those tasks (plus results that depended on them) and
    preserves every other result. The LLM is used only when the plan's
    structure genuinely has to change.
    """

    @staticmethod
    def replan(state: AgentState) -> Dict[str, Any]:
        old_plan: List[Dict[str, Any]] = [dict(task) for task in (state.get("plan") or [])]
        evaluation = state.get("evaluation") or {}
        failing_actions: Set[str] = set(evaluation.get("failing_actions") or [])
        issues: List[str] = list(evaluation.get("issues") or [])
        task_validation = state.get("task_validation") or {}
        action_history = list(state.get("action_history") or [])
        mode = evaluation.get("replan_mode") or "retry"

        if mode == "structural":
            unresolved = {a for a, r in task_validation.items() if r.get("status") == "unresolved"}
            try:
                new_plan, source = ReplannerAgent._structural_plan(state, old_plan, failing_actions, unresolved,
                                                                   issues, action_history)
            except TurnHalted as exc:
                action_history.append({"event": "replan_halted", "reason": exc.kind})
                return {
                    "action_history": action_history,
                    "turn_halt": {"kind": exc.kind, "detail": str(exc)[:300], "action": "replanner"},
                    "replan_required": False,
                }
        else:
            new_plan = ReplannerAgent._retry_plan(old_plan, failing_actions, task_validation)
            source = "deterministic"

        old_ids = {task["id"] for task in old_plan}
        retry_actions = sorted({t["action"] for t in new_plan if t.get("status") == "pending" and t["id"] not in old_ids})
        preserve_actions = sorted({t["action"] for t in new_plan if t.get("status") == "completed"})
        kept_ids = {task["id"] for task in new_plan if task.get("status") == "completed"}
        plan_version = (state.get("plan_version") or 1) + 1

        action_history.append({
            "event": "replanned",
            "source": source,
            "mode": mode,
            "plan_version": plan_version,
            "retry_tasks": retry_actions,
            "preserve_tasks": preserve_actions,
            # Kept for compatibility with earlier traces/tests.
            "redo_actions": retry_actions,
            "kept_actions": preserve_actions,
            "reason": state.get("replan_reason"),
        })

        selected_tools: List[str] = []
        for task in new_plan:
            if task["action"] not in selected_tools:
                selected_tools.append(task["action"])

        return {
            # goal / success_criteria are deliberately not returned: a replan
            # fixes execution, it never rewrites what the user asked for.
            "plan": new_plan,
            "plan_version": plan_version,
            "selected_tools": selected_tools,
            "completed_tasks": [t for t in (state.get("completed_tasks") or []) if t.get("id") in kept_ids],
            "failed_tasks": [t for t in (state.get("failed_tasks") or []) if t.get("action") not in retry_actions],
            # Only the retried tasks' current-attempt slot is cleared; their
            # best earlier result stays in best_results until a better one
            # is validated.
            "tool_results": {
                action: result
                for action, result in (state.get("tool_results") or {}).items()
                if action not in retry_actions
            },
            "current_task": None,
            "last_observation": None,
            "handoff_reason": None,
            "action_history": action_history,
            "replan_count": (state.get("replan_count") or 0) + 1,
            "replan_required": False,
            "replan_feedback": "; ".join(issues)[:800] or None,
        }

    @staticmethod
    def _retry_instruction(record: Dict[str, Any]) -> str:
        issues = "; ".join(i.rstrip(". ") for i in record.get("issues") or [])
        hints = " ".join(_RETRY_HINTS[c] for c in record.get("codes") or [] if c in _RETRY_HINTS)
        text = f"Previous attempt failed these checks: {issues}. Fix exactly these problems and keep everything else."
        return (text + (" " + hints if hints else ""))[:700]

    @staticmethod
    def _retry_plan(
        old_plan: List[Dict[str, Any]],
        failing_actions: Set[str],
        task_validation: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Deterministic minimal corrective plan: retry the failing tasks and
        anything that consumed their (now replaced) output; preserve the rest."""
        redo_ids: Set[str] = {task["id"] for task in old_plan if task["action"] in failing_actions}
        changed = True
        while changed:
            changed = False
            for task in old_plan:
                # completed dependents consumed the replaced output; skipped ones
                # never ran. Pending ones just wait for the new attempt.
                if task["id"] not in redo_ids and task.get("status") in ("completed", "skipped") \
                        and any(dep in redo_ids for dep in task.get("depends_on") or []):
                    redo_ids.add(task["id"])
                    changed = True

        next_index = _next_index(old_plan)
        new_ids: Dict[str, str] = {}
        for task in old_plan:
            if task["id"] in redo_ids:
                new_ids[task["id"]] = f"t{next_index}"
                next_index += 1

        new_plan: List[Dict[str, Any]] = []
        for task in old_plan:
            depends_on = [new_ids.get(dep, dep) for dep in task.get("depends_on") or []]
            if task["id"] not in redo_ids:
                new_plan.append({**task, "depends_on": depends_on})
                continue
            retried = {
                k: v for k, v in task.items()
                if k not in ("error", "failure_code", "missing_fields", "instruction")
            }
            retried.update({"id": new_ids[task["id"]], "status": "pending", "depends_on": depends_on})
            record = task_validation.get(task["action"]) or {}
            if task["action"] in failing_actions and record:
                retried["instruction"] = ReplannerAgent._retry_instruction(record)
            new_plan.append(retried)
        return new_plan

    @staticmethod
    def _structural_plan(
        state: AgentState,
        old_plan: List[Dict[str, Any]],
        failing_actions: Set[str],
        unresolved: Set[str],
        issues: List[str],
        action_history: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], str]:
        content = ReplannerAgent._ask_llm(state, old_plan, failing_actions, unresolved, issues, repair=None)
        parsed = extract_json_object(content) or {}
        new_plan, errors = ReplannerAgent._assemble(parsed, old_plan, failing_actions, unresolved)
        if errors:
            content = ReplannerAgent._ask_llm(state, old_plan, failing_actions, unresolved, issues,
                                              repair=(content, errors))
            parsed = extract_json_object(content) or {}
            new_plan, errors = ReplannerAgent._assemble(parsed, old_plan, failing_actions, unresolved)
        if errors:
            # Keep the plan as is: the blocked tasks stay skipped and the
            # evaluator reports the turn honestly as incomplete.
            action_history.append({"event": "replan_invalid", "errors": errors})
            return old_plan, "fallback"
        return new_plan, "llm"

    @staticmethod
    def _ask_llm(
        state: AgentState,
        old_plan: List[Dict[str, Any]],
        failing_actions: Set[str],
        unresolved: Set[str],
        issues: List[str],
        repair,
    ) -> str:
        llm = get_llm(temperature=0.0, purpose="router")

        capabilities = "\n".join(f"- '{tool['name']}': {tool['description']}" for tool in get_tools_metadata())
        results = state.get("tool_results") or {}

        def by_status(*statuses: str) -> str:
            names = [t["action"] for t in old_plan if t.get("status") in statuses]
            return ", ".join(names) or "none"

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are the replanning engine of a fitness planning agent. Part of the previous plan "
                "could not be completed and now blocks other tasks. Restructure ONLY the blocked work.\n\n"
                "Available capabilities:\n{capabilities}\n\n"
                "Rules:\n"
                "- List in 'keep' the completed capabilities whose results are still valid; they will NOT be re-run.\n"
                "- Never keep a capability named in Failing Actions.\n"
                "- 'tasks' is the work to run now. Every failed, failing, or unfinished capability must appear in it.\n"
                "- Do not redo valid completed work unless its input is being changed.\n"
                "- You may add a listed capability if the goal needs it; never invent capabilities.\n"
                "- Give each task a short 'instruction' saying exactly what to do differently.\n"
                "- depends_on uses capability names from 'keep' or 'tasks'; no self-dependencies or cycles.\n"
                "- Do not include capabilities that are blocked on user input.\n"
                "- Unresolved capabilities cannot be retried: never list them in 'tasks' and never depend on them. "
                "Plan the blocked tasks so they no longer need them, or leave them out.\n"
                "- The user's goal is fixed; do not restate or change it.\n\n"
                "Return ONLY a JSON object with this exact shape:\n"
                "{{\"keep\": [\"bmi\"], "
                "\"tasks\": [{{\"action\": \"diet\", \"depends_on\": [\"macros\"], \"instruction\": \"...\"}}]}}\n"
                "Do not return markdown, explanations, or code fences."
            )),
            ("user", (
                "User Message: {query}\n"
                "Goal: {goal}\n"
                "Success Criteria: {criteria}\n\n"
                "Current Plan: {plan}\n"
                "Completed: {completed}\n"
                "Failed / Unfinished: {unfinished}\n"
                "Blocked on user input: {blocked}\n"
                "Unresolved (cannot be retried): {unresolved}\n\n"
                "Results:\n{results}\n\n"
                "Evaluator Issues: {issues}\n"
                "Failing Actions: {failing}"
            )),
            ("placeholder", "{repair}"),
        ])

        repair_messages = []
        if repair:
            previous, errors = repair
            repair_messages = [
                ("assistant", previous[:1500]),
                ("user", "That plan is invalid: " + " ".join(errors)
                 + " Return a corrected JSON object with the same shape only."),
            ]

        response = call_llm(prompt | llm, {
            "capabilities": capabilities,
            "query": state.get("user_query") or "",
            "goal": state.get("goal") or "",
            "criteria": "; ".join(state.get("success_criteria") or []),
            "plan": json.dumps(
                [{k: t.get(k) for k in ("id", "action", "status", "depends_on")} for t in old_plan],
                ensure_ascii=False,
            ),
            "completed": by_status("completed"),
            "unfinished": by_status("failed", "skipped", "pending", "running"),
            "blocked": by_status("needs_input"),
            "unresolved": ", ".join(sorted(unresolved)) or "none",
            "results": "\n".join(
                f"- {action}: {summarize_result(result, 400)}" for action, result in results.items()
            ) or "none",
            "issues": "; ".join(issues) or "none",
            "failing": ", ".join(sorted(failing_actions)) or "none",
            "repair": repair_messages,
        })
        return (response.content or "").strip()

    @staticmethod
    def _assemble(
        parsed: Dict[str, Any],
        old_plan: List[Dict[str, Any]],
        failing_actions: Set[str],
        unresolved: Set[str],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Merge the LLM's new tasks with preserved results and validate."""
        errors: List[str] = []
        raw_tasks = parsed.get("tasks")
        if not isinstance(raw_tasks, list) or not raw_tasks:
            return [], ["'tasks' must be a non-empty list."]

        keep = parsed.get("keep") or []
        if not isinstance(keep, list):
            errors.append("'keep' must be a list.")
            keep = []
        for action in keep:
            if action in failing_actions:
                errors.append(f"'{action}' is failing and cannot be kept; it must be redone.")

        redo_names = {entry.get("action") for entry in raw_tasks if isinstance(entry, dict)}
        for action in sorted(redo_names & unresolved):
            errors.append(f"'{action}' is unresolved and cannot be retried this turn.")
        for entry in raw_tasks:
            if isinstance(entry, dict) and set(entry.get("depends_on") or []) & unresolved:
                errors.append(f"'{entry.get('action')}' cannot depend on unresolved capabilities.")
        # Preserve valid completed work by default: it is kept unless the
        # LLM explicitly schedules it again.
        kept = [
            task for task in old_plan
            if task.get("status") == "completed"
            and task["action"] not in failing_actions
            and task["action"] not in redo_names
        ]
        # needs_input tasks and unresolved attempts are carried unchanged so
        # the plan still shows them (unresolved ones are never re-run).
        carried = [
            task for task in old_plan
            if task["action"] not in redo_names and task not in kept
            and (task.get("status") == "needs_input" or task["action"] in unresolved)
        ]

        # A kept result whose dependency is being redone is stale: redo it too.
        action_by_id = {task["id"]: task["action"] for task in old_plan}
        extra_tasks: List[Dict[str, Any]] = []
        while True:
            available_ids = {task["id"] for task in kept + carried}
            stale = [t for t in kept if any(dep not in available_ids for dep in (t.get("depends_on") or []))]
            if not stale:
                break
            for task in stale:
                kept.remove(task)
                extra_tasks.append({
                    "action": task["action"],
                    "depends_on": [action_by_id.get(dep, dep) for dep in task.get("depends_on") or []],
                })

        new_tasks, build_errors = tasks_from_llm(
            list(raw_tasks) + extra_tasks, get_type_map(), start_index=_next_index(old_plan), existing=kept + carried,
        )
        errors.extend(build_errors)

        must_redo = {
            task["action"] for task in old_plan
            if task["action"] not in unresolved
            and (task.get("status") in ("failed", "skipped", "pending", "running")
                 or (task.get("status") == "completed" and task["action"] in failing_actions))
        }
        missing = must_redo - {task["action"] for task in new_tasks}
        if missing:
            errors.append(f"Failed/unfinished capabilities missing from tasks: {sorted(missing)}.")

        plan = kept + carried + new_tasks
        errors.extend(validate_plan(plan, get_all_tool_names()))
        return plan, errors
