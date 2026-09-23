import json
from typing import Any, Dict, List, Optional, Tuple


def extract_json_object(text: str) -> Optional[dict]:
    """Find the first top-level {...} object in `text` and parse it.

    Shared by any agent that asks the LLM for structured JSON (planner,
    evaluator): a naive non-greedy regex can't safely find the matching
    closing brace once the JSON has nested objects/lists, so this does a
    simple brace-depth scan instead.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        char = text[i]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    return None
    return None


# A task in one of these statuses will not be dispatched again this plan.
# "halted" = never finished because the turn stopped (rate limit / budget).
TERMINAL_STATUSES = {"completed", "failed", "skipped", "needs_input", "halted"}

# --- Task-level validation -------------------------------------------------
# validated: passed every check | unknown: produced, but the judge could not
# answer | failed: a check failed, retry allowed | unresolved: failed and the
# retry policy is exhausted (or the same failure repeated).
VALIDATION_RANK = {"validated": 3, "unknown": 2, "failed": 1, "unresolved": 1}


def validation_for(task: Dict[str, Any], task_validation: Dict[str, Any]) -> Optional[str]:
    """Validation status of THIS task attempt, or None if not yet evaluated."""
    record = task_validation.get(task.get("action")) or {}
    return record.get("status") if record.get("task_id") == task.get("id") else None


def needs_validation(task: Dict[str, Any], task_validation: Dict[str, Any]) -> bool:
    return task.get("status") == "completed" and validation_for(task, task_validation) is None


def dependency_blocked(dep: Optional[Dict[str, Any]], task_validation: Dict[str, Any]) -> bool:
    if dep is None:
        return False
    if dep.get("status") in ("failed", "skipped", "needs_input", "halted"):
        return True
    return validation_for(dep, task_validation) in ("failed", "unresolved")


def dependency_met(dep: Optional[Dict[str, Any]], task_validation: Dict[str, Any]) -> bool:
    return dep is not None and dep.get("status") == "completed" and not dependency_blocked(dep, task_validation)


def update_best(
    best_results: Dict[str, Dict[str, Any]],
    action: str,
    task_id: str,
    result: Any,
    validation: str,
) -> bool:
    """Keep the best result per action: a result only replaces the stored one
    when it validated at least as well. Returns True when it was stored."""
    if result is None:
        return False
    current = best_results.get(action)
    if current and VALIDATION_RANK.get(validation, 0) < VALIDATION_RANK.get(current.get("validation"), 0):
        return False
    best_results[action] = {"result": result, "validation": validation, "task_id": task_id}
    return True


def missing_profile_fields(profile: Any, required: List[str]) -> List[str]:
    """Profile fields a capability needs that the session hasn't supplied yet."""
    return [field for field in required if getattr(profile, field, None) in (None, "")]


def summarize_result(result: Any, limit: int = 300) -> str:
    """Compact, prompt-safe view of one task's result for LLM decisions."""
    if not isinstance(result, dict):
        return str(result)[:limit]
    parts = []
    for value in result.values():
        text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        parts.append(text.strip())
    return " ".join(parts)[:limit]


def tasks_from_llm(
    raw_tasks: Any,
    type_map: Dict[str, str],
    start_index: int = 1,
    existing: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Turn the LLM's [{"action", "depends_on": [...], "instruction"?}] list
    into plan tasks with ids.

    depends_on may name actions or task ids; action names are resolved
    against `existing` tasks (e.g. results kept across a replan) and the new
    tasks themselves. Nothing is dropped or silently repaired - anything
    malformed is reported so validate_plan()/the caller can reject it.
    """
    if not isinstance(raw_tasks, list):
        return [], ["'tasks' must be a list."]

    errors: List[str] = []
    id_by_action = {task["action"]: task["id"] for task in (existing or [])}
    new_tasks: List[Dict[str, Any]] = []

    for position, entry in enumerate(raw_tasks, start=1):
        if not isinstance(entry, dict) or not isinstance(entry.get("action"), str):
            errors.append(f"Task #{position} must be an object with an 'action' string.")
            continue
        action = entry["action"].strip()
        depends_on = entry.get("depends_on") or []
        if not isinstance(depends_on, list):
            errors.append(f"Task '{action}': depends_on must be a list.")
            depends_on = []

        task: Dict[str, Any] = {
            "id": f"t{start_index + len(new_tasks)}",
            "action": action,
            "type": type_map.get(action, "tool"),
            "status": "pending",
            "depends_on": [str(dep) for dep in depends_on],
        }
        instruction = entry.get("instruction")
        if isinstance(instruction, str) and instruction.strip():
            task["instruction"] = instruction.strip()[:500]

        if action in id_by_action:
            errors.append(f"Duplicate action '{action}'.")
        else:
            id_by_action[action] = task["id"]
        new_tasks.append(task)

    for task in new_tasks:
        task["depends_on"] = [id_by_action.get(dep, dep) for dep in task["depends_on"]]

    return new_tasks, errors


def validate_plan(plan: List[Dict[str, Any]], valid_actions: List[str]) -> List[str]:
    """Structural validation shared by planner and replanner: known
    actions, unique ids, no self/unresolved dependencies, no cycles."""
    if not plan:
        return ["Plan has no tasks."]

    errors: List[str] = []
    ids = [task.get("id") for task in plan]
    if len(set(ids)) != len(ids):
        errors.append("Task ids must be unique.")
    id_set = set(ids)

    for task in plan:
        task_id = task.get("id")
        if task.get("action") not in valid_actions:
            errors.append(f"Task {task_id}: unknown action '{task.get('action')}'.")
        for dep in task.get("depends_on") or []:
            if dep == task_id:
                errors.append(f"Task {task_id} ('{task.get('action')}') depends on itself.")
            elif dep not in id_set:
                errors.append(f"Task {task_id} ('{task.get('action')}') depends on '{dep}', which is not in the plan.")

    # Kahn's algorithm over resolvable edges: anything left unvisited is on a cycle.
    indegree = {task_id: 0 for task_id in id_set}
    dependents: Dict[str, List[str]] = {task_id: [] for task_id in id_set}
    for task in plan:
        for dep in set(task.get("depends_on") or []):
            if dep in id_set and dep != task["id"]:
                indegree[task["id"]] += 1
                dependents[dep].append(task["id"])
    queue = [task_id for task_id, degree in indegree.items() if degree == 0]
    visited = 0
    while queue:
        current = queue.pop()
        visited += 1
        for child in dependents[current]:
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if visited != len(id_set):
        cyclic = sorted(task_id for task_id, degree in indegree.items() if degree > 0)
        errors.append(f"Dependency cycle between tasks: {cyclic}.")

    return errors
