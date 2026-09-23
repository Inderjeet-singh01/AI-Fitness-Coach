"""
Standalone test harness for the agentic loop (planner -> executor ->
worker -> executor ... -> evaluator -> continue/replan/complete) and the
session API. This project has no test framework dependency (no pytest in
requirements.txt), so this is a plain assert-based script, run directly:

    .venv/bin/python3 backend/tests/test_agentic_loop.py

It monkeypatches models.llm.get_llm so every LLM call anywhere in the graph
(planner, executor decisions, evaluator's semantic check, replanner,
diet/workout/general workers) is
answered by a small scripted fake instead of hitting Groq. This lets the
whole plan -> execute -> evaluate -> replan -> complete loop run
deterministically and fully offline (no GROQ_API_KEY required).
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.runnables import RunnableLambda

import models.llm as llm_module


class FakeResponse:
    def __init__(self, content, finish_reason=None):
        self.content = content
        self.response_metadata = {"finish_reason": finish_reason} if finish_reason else {}


# --- Scripted behavior, mutated per test case ---
SCRIPT = {
    "planner_tasks": [],
    "planner_goal": "Test goal",
    "planner_success_criteria": ["Criterion"],
    "diet_calls": 0,
    "diet_bad_first": False,
    "diet_good_totals": (1800.0, 150),
    "diet_bad_totals": (1800.0, 75),
    # Planner: optional list of raw responses returned in order before
    # falling back to the scripted tasks (used for invalid-plan tests).
    "planner_raw": [],
    "planner_calls": 0,
    # Executor: fn(prompt_text, options) -> choice; default = first option.
    "executor_choice": None,
    "executor_calls": 0,
    "executor_prompts": [],
    # Replanner: optional list of raw responses; default emulates a
    # sensible LLM (redo failing/unfinished, keep the rest).
    "replan_raw": [],
    "replan_calls": 0,
    # Diet: optional scripted outputs popped per call; each is a string or
    # (content, finish_reason).
    "diet_outputs": [],
    "diet_prompts": [],
    "workout_calls": 0,
    # Judge (evaluator): optional raw responses popped per call; default pass.
    "judge_outputs": [],
    "judge_calls": 0,
    "judge_kinds": [],
    "judge_prompts": [],
    # role -> exception raised on every call for that role (e.g. a 429).
    "raise_for": {},
    "llm_calls": 0,
}


def _reset_script():
    SCRIPT["planner_tasks"] = []
    SCRIPT["planner_goal"] = "Test goal"
    SCRIPT["planner_success_criteria"] = ["Criterion"]
    SCRIPT["diet_calls"] = 0
    SCRIPT["diet_bad_first"] = False
    SCRIPT["diet_good_totals"] = (1800.0, 150)
    SCRIPT["diet_bad_totals"] = (1800.0, 75)
    SCRIPT["planner_raw"] = []
    SCRIPT["planner_calls"] = 0
    SCRIPT["executor_choice"] = None
    SCRIPT["executor_calls"] = 0
    SCRIPT["executor_prompts"] = []
    SCRIPT["replan_raw"] = []
    SCRIPT["replan_calls"] = 0
    SCRIPT["diet_outputs"] = []
    SCRIPT["diet_prompts"] = []
    SCRIPT["workout_calls"] = 0
    SCRIPT["judge_outputs"] = []
    SCRIPT["judge_calls"] = 0
    SCRIPT["judge_kinds"] = []
    SCRIPT["judge_prompts"] = []
    SCRIPT["raise_for"] = {}
    SCRIPT["llm_calls"] = 0


ROLE_MARKERS = [
    ("execution controller of a fitness planning agent", "executor"),
    ("replanning engine of a fitness planning agent", "replanner"),
    ("advanced planning engine", "planner"),
    ("evaluation stage of a fitness planning agent", "judge"),
    ("sports nutrition and fitness diet planning assistant", "diet"),
    ("expert fitness coach specialized in personalized workout plans", "workout"),
    ("professional fitness-only conversational assistant", "general"),
]


def _role(text: str) -> str:
    return next((role for marker, role in ROLE_MARKERS if marker in text), "unknown")


def _prompt_text(prompt_value) -> str:
    messages = prompt_value.to_messages() if hasattr(prompt_value, "to_messages") else []
    return "\n".join(str(getattr(m, "content", "")) for m in messages)


def _line_value(text: str, label: str) -> str:
    match = re.search(rf"^{re.escape(label)}:\s*(.*)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def _names(value: str):
    return [] if value in ("", "none") else [v.strip() for v in value.split(",") if v.strip()]


def _fake_replanner(text: str) -> str:
    failing = _names(_line_value(text, "Failing Actions"))
    unfinished = _names(_line_value(text, "Failed / Unfinished"))
    completed = _names(_line_value(text, "Completed"))
    deps = {t["action"]: t.get("depends_on", []) for t in SCRIPT["planner_tasks"]}
    redo = list(dict.fromkeys(failing + unfinished))
    return json.dumps({
        "goal": SCRIPT["planner_goal"],
        "success_criteria": SCRIPT["planner_success_criteria"],
        "keep": [a for a in completed if a not in failing],
        "tasks": [
            {"action": a, "depends_on": deps.get(a, []), "instruction": f"LLM fix for {a}"}
            for a in redo
        ],
    })


def _fake_responder(text: str) -> str:
    if "execution controller of a fitness planning agent" in text:
        SCRIPT["executor_calls"] += 1
        SCRIPT["executor_prompts"].append(text)
        options = _names(_line_value(text, "Options"))
        chooser = SCRIPT["executor_choice"]
        return json.dumps({"next": chooser(text, options) if chooser else options[0]})

    if "replanning engine of a fitness planning agent" in text:
        SCRIPT["replan_calls"] += 1
        if SCRIPT["replan_raw"]:
            return SCRIPT["replan_raw"].pop(0)
        return _fake_replanner(text)

    if "advanced planning engine" in text:
        SCRIPT["planner_calls"] += 1
        if SCRIPT["planner_raw"]:
            return SCRIPT["planner_raw"].pop(0)
        return json.dumps({
            "goal": SCRIPT["planner_goal"],
            "success_criteria": SCRIPT["planner_success_criteria"],
            "tasks": SCRIPT["planner_tasks"],
        })

    if "evaluation stage of a fitness planning agent" in text:
        SCRIPT["judge_calls"] += 1
        SCRIPT["judge_prompts"].append(text)
        kind = re.search(r"Judge ONE generated (\w+)", text)
        SCRIPT["judge_kinds"].append(kind.group(1) if kind else "?")
        if SCRIPT["judge_outputs"]:
            return SCRIPT["judge_outputs"].pop(0)
        return json.dumps({"status": "pass", "failed_checks": [], "issues": []})

    if "sports nutrition and fitness diet planning assistant" in text:
        SCRIPT["diet_calls"] += 1
        SCRIPT["diet_prompts"].append(text)
        if SCRIPT["diet_outputs"]:
            return SCRIPT["diet_outputs"].pop(0)
        use_bad = SCRIPT["diet_bad_first"] and SCRIPT["diet_calls"] == 1
        calories, protein = SCRIPT["diet_bad_totals"] if use_bad else SCRIPT["diet_good_totals"]
        return (
            "## Day 1\n- Sample balanced meals for the day\n\n"
            f"**Daily Totals:** ~{calories} kcal | Protein: {protein}g | Carbs: 150g | Fats: 50g"
        )

    if "expert fitness coach specialized in personalized workout plans" in text:
        SCRIPT["workout_calls"] += 1
        return "## Day 1\n- Squats 3x10\n- Push-ups 3x10\n- Plank 3x30s"

    if "professional fitness-only conversational assistant" in text:
        return "Hey! Happy to help with your fitness goals."

    return "{}"


def _fake_get_llm(*args, **kwargs):
    def _invoke(prompt_value, config=None, **kw):
        text = _prompt_text(prompt_value)
        SCRIPT["llm_calls"] += 1
        error = SCRIPT["raise_for"].get(_role(text))
        if error is not None:
            raise error
        output = _fake_responder(text)
        if isinstance(output, tuple):
            return FakeResponse(*output)
        return FakeResponse(output)
    return RunnableLambda(_invoke)


llm_module.get_llm = _fake_get_llm

# Import agent/tool modules AFTER patching models.llm.get_llm so their
# `from models.llm import get_llm` binds to the fake. Re-assigning the name
# on each module afterwards is redundant-but-safe insurance against import
# order surprises.
import agents.planner as planner_module  # noqa: E402
import agents.executor as executor_module  # noqa: E402
import agents.evaluator as evaluator_module  # noqa: E402
import agents.replanner as replanner_module  # noqa: E402
import tools.diet_generator as diet_module  # noqa: E402
import tools.workout_generator as workout_module  # noqa: E402
import tools.general_tool as general_module  # noqa: E402

for _mod in (planner_module, executor_module, evaluator_module, replanner_module,
             diet_module, workout_module, general_module):
    _mod.get_llm = _fake_get_llm

import graph.workflow as workflow_module  # noqa: E402
from graph.workflow import app_graph, run_config  # noqa: E402
from schemas.schemas import UserProfileData  # noqa: E402
from config.settings import settings  # noqa: E402
from agents.common import validate_plan  # noqa: E402
from tools.registry import get_all_tool_names  # noqa: E402


PASS = []
FAIL = []


def check(name, condition, detail=""):
    if condition:
        PASS.append(name)
        print(f"PASS: {name}")
    else:
        FAIL.append(name)
        print(f"FAIL: {name} -- {detail}")


def new_session(profile_kwargs=None):
    """Create a session through the real API route logic."""
    import asyncio
    from api.routes import create_session
    from schemas.schemas import SessionCreateRequest

    request = SessionCreateRequest(profile=UserProfileData(**(profile_kwargs or {})))
    response = asyncio.run(create_session(request))
    return response.session_id, run_config(response.session_id)


def send_turn(config, message, tasks):
    """tasks: list of {"action":..., "depends_on":[...]} for the fake planner to emit.
    Sends exactly what the chat route sends: only the new message."""
    SCRIPT["planner_tasks"] = tasks
    turn_input = {
        "user_query": message,
        "messages": [{"role": "user", "content": message}],
    }
    return app_graph.invoke(turn_input, config=config)


def events(result, name):
    return [e for e in result.get("action_history", []) if e.get("event") == name]


def executed(result):
    return [e["action"] for e in events(result, "completed")]


def full_profile():
    return {
        "weight_kg": 80, "height_cm": 175, "age": 28, "gender": "male",
        "activity_level": "moderately_active",
    }


def compute_macro_target(profile: UserProfileData, query: str):
    """Mirrors tools/macro_tool.py's math so tests can script diet outputs
    that deterministically pass or fail the evaluator's tolerance check."""
    w, h, a, g = profile.weight_kg, profile.height_cm, profile.age, profile.gender
    if g == "male":
        bmr = (10 * w) + (6.25 * h) - (5 * a) + 5
    elif g == "female":
        bmr = (10 * w) + (6.25 * h) - (5 * a) - 161
    else:
        bmr = (10 * w) + (6.25 * h) - (5 * a) - 78
    multipliers = {"sedentary": 1.2, "lightly_active": 1.375, "moderately_active": 1.55, "very_active": 1.725}
    tdee = bmr * multipliers.get(profile.activity_level, 1.2)
    q = query.lower()
    if any(k in q for k in ["lose", "fat loss", "weight loss", "cutting", "lean"]):
        target = tdee - 500
    elif any(k in q for k in ["gain", "muscle gain", "bulking", "mass"]):
        target = tdee + 300
    else:
        target = tdee
    protein_g = round(w * 2.0)
    return round(target, 2), protein_g


# --- A: simple query -> only the required capability executes ---
def test_a_simple_bmi():
    _reset_script()
    _, config = new_session(full_profile())
    result = send_turn(config, "Calculate my BMI.", [{"action": "bmi", "depends_on": []}])
    check("A: bmi result present for this turn", (result.get("tool_results") or {}).get("bmi") is not None)
    check("A: only bmi executed", executed(result) == ["bmi"], executed(result))
    check("A: final_status success + goal_completed", result.get("final_status") == "success"
          and result.get("goal_completed") is True, result.get("evaluation"))
    check("A: single valid task -> no executor LLM call", SCRIPT["executor_calls"] == 0, SCRIPT["executor_calls"])
    check("A: no replans", result.get("replan_count", 0) == 0)


# --- B/C: full request -> structured plan executes, evaluator passes it ---
def test_b_c_full_report_success():
    _reset_script()
    profile = UserProfileData(**full_profile())
    query = "Create my complete weight-loss plan."
    target_cal, target_protein = compute_macro_target(profile, query)
    SCRIPT["diet_good_totals"] = (target_cal, target_protein)

    _, config = new_session(full_profile())
    tasks = [
        {"action": "bmi", "depends_on": []},
        {"action": "water", "depends_on": []},
        {"action": "macros", "depends_on": ["bmi"]},
        {"action": "diet", "depends_on": ["macros"]},
        {"action": "workout", "depends_on": []},
    ]
    result = send_turn(config, query, tasks)
    plan = result.get("plan") or []
    check("B: structured plan with ids + resolved deps",
          [t["id"] for t in plan] == ["t1", "t2", "t3", "t4", "t5"]
          and plan[2]["depends_on"] == ["t1"] and plan[3]["depends_on"] == ["t3"], plan)
    check("B: every planned capability executed", sorted(executed(result)) == sorted(t["action"] for t in tasks),
          executed(result))
    check("B: macros ran after bmi, diet after macros",
          executed(result).index("bmi") < executed(result).index("macros") < executed(result).index("diet"))
    check("B: executor used the router LLM when several generative tasks were runnable",
          SCRIPT["executor_calls"] >= 1, SCRIPT["executor_calls"])
    check("C: goal complete -> success", result.get("final_status") == "success"
          and result.get("goal_completed") is True, result.get("evaluation"))
    report = result.get("final_report") or ""
    check("B/C: report contains this turn's sections", "Nutrition Plan" in report and "Workout Plan" in report)
    check("B/C: no replan needed", result.get("replan_count", 0) == 0)


# --- N: next action depends on the previous result ---
def test_n_next_action_depends_on_result():
    # (1) The LLM decision sees the latest result and picks accordingly.
    def choose_by_bmi(text, options):
        wants_diet_first = "Obese" in text
        order = {"diet": "t2", "workout": "t3"}
        return order["diet"] if wants_diet_first else order["workout"]

    orders = {}
    for label, profile in (("obese", {**full_profile(), "weight_kg": 130}), ("normal", full_profile())):
        _reset_script()
        SCRIPT["executor_choice"] = choose_by_bmi
        SCRIPT["diet_good_totals"] = (None, None)
        _, config = new_session(profile)
        result = send_turn(config, "Check my BMI then give me a workout and a meal idea.", [
            {"action": "bmi", "depends_on": []},
            {"action": "diet", "depends_on": []},
            {"action": "workout", "depends_on": []},
        ])
        orders[label] = executed(result)
        check(f"N1[{label}]: decision prompt contained the bmi observation",
              any("bmi" in p and "bmi_value" in p for p in SCRIPT["executor_prompts"]))
    check("N1: different bmi result -> different next action",
          orders["obese"][1] == "diet" and orders["normal"][1] == "workout", orders)

    # (2) After a failure the executor stops early instead of running the rest.
    _reset_script()
    original = workflow_module.RUN_FN_BY_ACTION["bmi"]
    calls = {"n": 0}

    def flaky_bmi(state):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("temporary calculation fault")
        return original(state)

    SCRIPT["executor_choice"] = lambda text, options: "evaluate" if "FAILED" in text else options[0]
    workflow_module.RUN_FN_BY_ACTION["bmi"] = flaky_bmi
    try:
        _, config = new_session(full_profile())
        result = send_turn(config, "Calculate my BMI and give me a workout.", [
            {"action": "bmi", "depends_on": []},
            {"action": "workout", "depends_on": []},
        ])
    finally:
        workflow_module.RUN_FN_BY_ACTION["bmi"] = original

    history = result.get("action_history", [])
    first_replan = next(i for i, e in enumerate(history) if e.get("event") == "replanned")
    workout_runs = [i for i, e in enumerate(history) if e.get("event") == "completed" and e.get("action") == "workout"]
    check("N2: after bmi failed, LLM chose to stop -> workout did not run before replan",
          workout_runs and all(i > first_replan for i in workout_runs), history)
    check("N2: recovered after replan -> success", result.get("final_status") == "success", result.get("evaluation"))


# --- D/E: failed diet -> deterministic task-level replan, only diet redone ---
def test_d_e_replan_diet_only():
    _reset_script()
    profile = UserProfileData(**full_profile())
    query = "Give me my calories and a diet plan."
    target_cal, target_protein = compute_macro_target(profile, query)
    SCRIPT["diet_bad_first"] = True
    SCRIPT["diet_good_totals"] = (target_cal, target_protein)
    SCRIPT["diet_bad_totals"] = (target_cal, round(target_protein * 0.5))  # well under target

    _, config = new_session(full_profile())
    tasks = [
        {"action": "bmi", "depends_on": []},
        {"action": "macros", "depends_on": ["bmi"]},
        {"action": "diet", "depends_on": ["macros"]},
    ]
    result = send_turn(config, query, tasks)

    check("D: evaluator detects the protein mismatch, replans, then succeeds",
          result.get("final_status") == "success" and result.get("goal_completed") is True, result.get("evaluation"))
    check("D: simple failure -> deterministic replan, no replanner LLM call", SCRIPT["replan_calls"] == 0,
          SCRIPT["replan_calls"])
    replanned = events(result, "replanned")
    check("D: replan recorded as deterministic retry",
          replanned and replanned[0]["source"] == "deterministic" and replanned[0]["mode"] == "retry", replanned)
    diet_task = next(t for t in result["plan"] if t["action"] == "diet")
    check("D: retried diet is a NEW task carrying its own failure as instruction",
          diet_task["id"] == "t4" and "protein" in (diet_task.get("instruction") or "").lower()
          and diet_task["depends_on"] == ["t2"], diet_task)
    check("D: retry prompt told the diet LLM what to fix",
          "below the minimum" in SCRIPT["diet_prompts"][-1], SCRIPT["diet_prompts"][-1][-400:])
    check("D: exactly one replan happened", result.get("replan_count") == 1, result.get("replan_count"))
    check("E: plan_version incremented on replan", result.get("plan_version") == 2, result.get("plan_version"))
    check("D: final diet protein matches target",
          f"Protein: {target_protein}g" in (result["tool_results"]["diet"]["diet_plan"]), result.get("tool_results"))
    check("E: replan retried only 'diet'",
          replanned and replanned[0]["retry_tasks"] == ["diet"] and replanned[0]["preserve_tasks"] == ["bmi", "macros"],
          replanned)
    check("E: bmi/macros preserved, executed exactly once",
          executed(result).count("bmi") == 1 and executed(result).count("macros") == 1, executed(result))
    check("D: judge only ran on the diet that passed the Python checks", SCRIPT["judge_calls"] == 1,
          SCRIPT["judge_calls"])
    check("D: goal/success criteria untouched by replanning", result.get("goal") == SCRIPT["planner_goal"])


# --- R: structural replan (unresolved task blocks dependents) -> LLM ---
def test_r_structural_replan():
    original = workflow_module.RUN_FN_BY_ACTION["bmi"]

    def broken_bmi(state):
        raise RuntimeError("calculation fault")

    tasks = [{"action": "bmi", "depends_on": []}, {"action": "macros", "depends_on": ["bmi"]}]

    # R1: invalid LLM replans -> one repair -> fallback keeps plan, honest incomplete.
    _reset_script()
    SCRIPT["replan_raw"] = [
        json.dumps({"keep": [], "tasks": [{"action": "bmi", "depends_on": []},
                                          {"action": "macros", "depends_on": ["bmi"]}]}),
        json.dumps({"tasks": [{"action": "macros", "depends_on": ["general"]},
                              {"action": "general", "depends_on": ["macros"]}]}),
    ]
    workflow_module.RUN_FN_BY_ACTION["bmi"] = broken_bmi
    try:
        _, config = new_session(full_profile())
        result = send_turn(config, "My BMI and macros.", tasks)
    finally:
        workflow_module.RUN_FN_BY_ACTION["bmi"] = original
    invalid = events(result, "replan_invalid")
    validation = result.get("task_validation") or {}
    check("R1: same bmi error twice -> bmi unresolved (repeated), not retried again",
          validation.get("bmi", {}).get("status") == "unresolved"
          and validation["bmi"].get("stop_reason") == "repeated"
          and executed(result).count("bmi") == 0 and len(events(result, "failed")) == 2, validation.get("bmi"))
    check("R1: structural replan used the LLM; invalid answers rejected after one repair",
          SCRIPT["replan_calls"] == 2 and invalid
          and any("cycle" in e.lower() for e in invalid[0]["errors"]), invalid)
    plan_ = [{"id": "t3", "action": "bmi", "type": "tool", "status": "failed", "depends_on": []},
             {"id": "t4", "action": "macros", "type": "tool", "status": "skipped", "depends_on": ["t3"]}]
    _, errors_ = replanner_module.ReplannerAgent._assemble(
        {"tasks": [{"action": "bmi", "depends_on": []}, {"action": "macros", "depends_on": ["bmi"]}]},
        plan_, {"macros"}, {"bmi"})
    check("R1: an LLM plan that retries or depends on an unresolved task is rejected",
          any("unresolved and cannot be retried" in e for e in errors_)
          and any("cannot depend on unresolved" in e for e in errors_), errors_)
    check("R1: fallback recorded, turn honestly incomplete",
          events(result, "replanned")[-1]["source"] == "fallback" and result.get("final_status") == "incomplete"
          and result.get("goal_completed") is False, result.get("final_status"))
    check("R1: did not burn MAX_REPLANS", result.get("replan_count") == 2, result.get("replan_count"))

    # R2: valid LLM restructure -> macros runs without bmi; goal is not rewritten.
    _reset_script()
    SCRIPT["replan_raw"] = [json.dumps({
        "goal": "SOMETHING ELSE", "success_criteria": ["changed"], "keep": [],
        "tasks": [{"action": "macros", "depends_on": [], "instruction": "compute BMR directly"}],
    })]
    workflow_module.RUN_FN_BY_ACTION["bmi"] = broken_bmi
    try:
        _, config = new_session(full_profile())
        result = send_turn(config, "My BMI and macros.", tasks)
    finally:
        workflow_module.RUN_FN_BY_ACTION["bmi"] = original
    check("R2: restructured plan ran macros without the unresolved bmi",
          executed(result) == ["macros"] and events(result, "replanned")[-1]["source"] == "llm", executed(result))
    check("R2: LLM replanner could not rewrite goal/success criteria",
          result.get("goal") == SCRIPT["planner_goal"]
          and result.get("success_criteria") == SCRIPT["planner_success_criteria"], result.get("goal"))
    check("R2: bmi still unresolved -> incomplete, macros shown",
          result.get("final_status") == "incomplete" and "Daily calories" in (result.get("final_report") or ""),
          result.get("final_status"))


# --- F: different failures may be retried up to MAX_TASK_RETRIES ---
def test_f_second_replan_increments_version():
    _reset_script()
    SCRIPT["judge_outputs"] = [
        json.dumps({"status": "fail", "failed_checks": ["goal"], "issues": ["Workout ignores fat loss."]}),
        json.dumps({"status": "fail", "failed_checks": ["constraints"], "issues": ["Needs a gym it can't assume."]}),
    ]
    _, config = new_session(full_profile())
    result = send_turn(config, "Create a workout plan for fat loss.", [{"action": "workout", "depends_on": []}])

    check("F: goal_completed True after two replans", result.get("goal_completed") is True, result.get("evaluation"))
    check("F: replan_count == 2", result.get("replan_count") == 2, result.get("replan_count"))
    check("F: plan_version == 3 (1 initial + 2 replans)", result.get("plan_version") == 3, result.get("plan_version"))
    check("F: 3 workout attempts, each judged once", SCRIPT["workout_calls"] == 3 and SCRIPT["judge_calls"] == 3)

    # Next turn resets per-turn counters and task-level state.
    result2 = send_turn(config, "hi", [{"action": "general", "depends_on": []}])
    check("F: new turn resets plan_version/replan_count/steps",
          result2.get("plan_version") == 1 and result2.get("replan_count") == 0
          and result2.get("execution_steps") == 1, (result2.get("plan_version"), result2.get("replan_count")))
    check("F: new turn resets task validation / best results / LLM counters",
          list((result2.get("task_validation") or {}).keys()) == ["general"]
          and list((result2.get("best_results") or {}).keys()) == ["general"]
          and result2.get("llm_calls") == 2, (result2.get("task_validation"), result2.get("llm_calls")))


# --- G: same failure repeated -> stop early, keep best, honest status ---
def test_g_repeated_failure_stops_early():
    _reset_script()
    SCRIPT["judge_outputs"] = [
        json.dumps({"status": "fail", "failed_checks": ["goal"], "issues": ["Always fails for this test."]})
    ] * 5
    _, config = new_session(full_profile())
    result = send_turn(config, "Create a workout plan.", [{"action": "workout", "depends_on": []}])

    check("G: goal_completed False (does not claim false success)", result.get("goal_completed") is False)
    check("G: stopped after the same reason repeated (not at MAX_REPLANS)",
          result.get("replan_count") == 1 and SCRIPT["workout_calls"] == 2 and SCRIPT["judge_calls"] == 2,
          (result.get("replan_count"), SCRIPT["workout_calls"], SCRIPT["judge_calls"]))
    check("G: final_status 'incomplete'", result.get("final_status") == "incomplete", result.get("final_status"))
    report = result.get("final_report") or ""
    check("G: report keeps the best workout and explains why",
          "Workout Plan" in report and "same problem repeated" in report, report[-300:])


# --- G2: MAX_REPLANS still caps a task that keeps failing differently ---
def test_g2_max_replan_protection():
    _reset_script()
    checks = ["goal", "constraints", "structure", "safety", "goal", "constraints"]
    SCRIPT["judge_outputs"] = [
        json.dumps({"status": "fail", "failed_checks": [c], "issues": [f"Fails on {c}."]}) for c in checks
    ]
    original_retries = settings.MAX_TASK_RETRIES
    settings.MAX_TASK_RETRIES = 10
    try:
        _, config = new_session(full_profile())
        result = send_turn(config, "Create a workout plan.", [{"action": "workout", "depends_on": []}])
    finally:
        settings.MAX_TASK_RETRIES = original_retries
    check("G2: stopped exactly at MAX_REPLANS", result.get("replan_count") == settings.MAX_REPLANS,
          (result.get("replan_count"), settings.MAX_REPLANS))
    check("G2: incomplete + limit explained", result.get("final_status") == "incomplete"
          and "replanning limit" in (result.get("final_report") or ""), result.get("final_report"))


PUNJABI_QUERY = "i am vegetarian and only afford cheap diet, diet must be according to Punjabi culture"
PUNJABI_DIET = (
    "## Punjabi Vegetarian Budget Plan\n"
    "- Breakfast: 2 missi roti with dahi\n"
    "- Lunch: rajma chawal with salad\n"
    "- Snack: roasted chana\n"
    "- Dinner: sarson da saag, makki di roti, paneer bhurji\n\n"
    "**Estimated Daily Cost:** ~₹120\n"
    "**Daily Totals:** ~2100 kcal | Protein: 95g | Carbs: 300g | Fats: 60g"
)


def honest(result) -> bool:
    """Success <=> no caveat; anything else must carry a note."""
    report = result.get("final_report") or ""
    if result.get("goal_completed"):
        return result.get("final_status") == "success" and "## Note" not in report
    return result.get("final_status") != "success" and "## Note" in report


# --- P: diet-only request with explicit, checkable constraints ---
def test_p_diet_only_constraints():
    _reset_script()
    SCRIPT["diet_outputs"] = [PUNJABI_DIET]
    _, config = new_session(full_profile())
    result = send_turn(config, PUNJABI_QUERY, [{"action": "diet", "depends_on": []}])
    check("P: constraints extracted as structured fields",
          result.get("constraints") == {"diet_type": "vegetarian", "cuisine": "Punjabi", "budget": "low",
                                        "daily_cost_required": True}, result.get("constraints"))
    check("P: success on first pass", result.get("final_status") == "success" and honest(result), result.get("evaluation"))
    check("P: 3 LLM calls (planner, diet, judge); no router/replanner",
          SCRIPT["llm_calls"] == 3 and result.get("llm_calls") == 3 and SCRIPT["executor_calls"] == 0
          and SCRIPT["replan_calls"] == 0, (SCRIPT["llm_calls"], result.get("llm_calls")))
    check("P: judge asked a named cuisine check, not a vague 'cheap' judgment",
          "cuisine: Most meals are recognisable Punjabi dishes" in SCRIPT["judge_prompts"][0]
          and "daily_cost: must be stated" in SCRIPT["diet_prompts"][0], SCRIPT["judge_prompts"][0][:600])

    # Missing cost line / non-veg item are caught in Python, then fixed on retry.
    _reset_script()
    SCRIPT["diet_outputs"] = [PUNJABI_DIET.replace("**Estimated Daily Cost:** ~₹120\n", "")
                              .replace("paneer bhurji", "chicken curry"), PUNJABI_DIET]
    _, config = new_session(full_profile())
    result = send_turn(config, PUNJABI_QUERY, [{"action": "diet", "depends_on": []}])
    first = (result.get("task_validation") or {}).get("diet", {}).get("history", [{}])[0]
    check("P: missing daily cost + non-vegetarian item flagged deterministically",
          first.get("codes") == ["diet.missing_daily_cost", "diet.not_vegetarian"], first)
    check("P: retried once, then success; judge only saw the valid attempt",
          result.get("final_status") == "success" and SCRIPT["diet_calls"] == 2 and SCRIPT["judge_calls"] == 1,
          (result.get("final_status"), SCRIPT["diet_calls"], SCRIPT["judge_calls"]))

    # Previous-turn macros are NOT used to judge a diet-only turn.
    _reset_script()
    _, config = new_session(full_profile())
    send_turn(config, "give me my calories and macros", [{"action": "macros", "depends_on": []}])
    SCRIPT["diet_outputs"] = [PUNJABI_DIET]
    result = send_turn(config, PUNJABI_QUERY, [{"action": "diet", "depends_on": []}])
    check("P: stale session macros not used (95g protein vs old 160g target still passes)",
          result.get("final_status") == "success" and "Macro Data: {}" in SCRIPT["diet_prompts"][-1],
          result.get("evaluation"))


FULL_TASKS = [
    {"action": "bmi", "depends_on": []},
    {"action": "water", "depends_on": []},
    {"action": "macros", "depends_on": ["bmi"]},
    {"action": "diet", "depends_on": ["macros"]},
    {"action": "workout", "depends_on": []},
    {"action": "gym", "depends_on": []},
]
FULL_QUERY = "generate full plan which make me fit according to my body, which contain everything"


def _with_fake_gym(fn):
    original = workflow_module.RUN_FN_BY_ACTION["gym"]
    workflow_module.RUN_FN_BY_ACTION["gym"] = lambda state: {"gym_data": "1. Fit Zone - 0.8 km"}
    try:
        return fn()
    finally:
        workflow_module.RUN_FN_BY_ACTION["gym"] = original


# --- Q: full plan first-pass success; each task evaluated exactly once ---
def test_q_full_plan_first_pass():
    _reset_script()
    profile = UserProfileData(**full_profile())
    target_cal, target_protein = compute_macro_target(profile, FULL_QUERY)
    SCRIPT["diet_good_totals"] = (target_cal, target_protein)
    _, config = new_session({**full_profile(), "location": "Mohali"})
    result = _with_fake_gym(lambda: send_turn(config, FULL_QUERY, FULL_TASKS))
    validation = result.get("task_validation") or {}
    check("Q: full plan success on first pass", result.get("final_status") == "success" and honest(result),
          result.get("evaluation"))
    check("Q: every task validated", sorted(validation) == sorted(t["action"] for t in FULL_TASKS)
          and all(v["status"] == "validated" for v in validation.values()), validation)
    check("Q: diet and workout judged once each, independently", SCRIPT["judge_kinds"] == ["diet", "workout"],
          SCRIPT["judge_kinds"])
    check("Q: 7 LLM calls = planner + 2 router + diet + judge + workout + judge",
          SCRIPT["llm_calls"] == 7 and SCRIPT["executor_calls"] == 2 and result.get("llm_calls") == 7,
          (SCRIPT["llm_calls"], SCRIPT["executor_calls"], result.get("llm_calls")))


# --- T: diet fails in a full plan -> only diet retried, nothing re-judged ---
def test_t_full_plan_diet_retry():
    _reset_script()
    profile = UserProfileData(**full_profile())
    target_cal, target_protein = compute_macro_target(profile, FULL_QUERY)
    SCRIPT["diet_bad_first"] = True
    SCRIPT["diet_good_totals"] = (target_cal, target_protein)
    SCRIPT["diet_bad_totals"] = (target_cal, round(target_protein * 0.5))
    _, config = new_session({**full_profile(), "location": "Mohali"})
    result = _with_fake_gym(lambda: send_turn(config, FULL_QUERY, FULL_TASKS))
    replanned = events(result, "replanned")
    check("T: success after retrying diet only", result.get("final_status") == "success", result.get("evaluation"))
    check("T: task-level replan {retry: diet, preserve: rest}",
          len(replanned) == 1 and replanned[0]["retry_tasks"] == ["diet"]
          and replanned[0]["preserve_tasks"] == ["bmi", "gym", "macros", "water", "workout"], replanned)
    check("T: workout/gym generated once; workout judged once; diet judged only when valid",
          SCRIPT["workout_calls"] == 1 and executed(result).count("gym") == 1
          and SCRIPT["judge_kinds"] == ["workout", "diet"], (SCRIPT["workout_calls"], SCRIPT["judge_kinds"]))
    check("T: no replanner LLM call", SCRIPT["replan_calls"] == 0)


# --- O: empty / truncated LLM output is a task failure, never "completed" ---
def test_o_empty_and_truncated_output():
    _reset_script()
    SCRIPT["diet_outputs"] = ["", PUNJABI_DIET]
    _, config = new_session(full_profile())
    result = send_turn(config, PUNJABI_QUERY, [{"action": "diet", "depends_on": []}])
    failed = events(result, "failed")
    check("O1: empty diet output recorded as failure (output.empty), not completed",
          failed and failed[0]["code"] == "output.empty" and executed(result) == ["diet"], failed)
    check("O1: empty attempt never reached the judge", SCRIPT["judge_calls"] == 1, SCRIPT["judge_calls"])
    check("O1: retry instruction mentions the empty answer; then success",
          "was empty" in SCRIPT["diet_prompts"][-1] and result.get("final_status") == "success")

    _reset_script()
    SCRIPT["diet_outputs"] = [("## Punjabi Plan\n- Breakfast: 2 missi roti", "length"), PUNJABI_DIET]
    _, config = new_session(full_profile())
    result = send_turn(config, PUNJABI_QUERY, [{"action": "diet", "depends_on": []}])
    failed = events(result, "failed")
    check("O2: finish_reason=length recorded as output.truncated", failed and failed[0]["code"] == "output.truncated",
          failed)
    check("O2: truncated text never stored as a result/best result",
          "missi roti\n" not in json.dumps(result.get("best_results")) and SCRIPT["judge_calls"] == 1)
    check("O2: retry asked for a shorter answer; then success",
          "cut off" in SCRIPT["diet_prompts"][-1] and result.get("final_status") == "success")


# --- U: evaluator UNKNOWN never regenerates and never claims success ---
def test_u_evaluator_unknown():
    _reset_script()
    SCRIPT["diet_outputs"] = [PUNJABI_DIET]
    SCRIPT["judge_outputs"] = [""]  # judge returned nothing usable
    _, config = new_session(full_profile())
    result = send_turn(config, PUNJABI_QUERY, [{"action": "diet", "depends_on": []}])
    check("U: unreadable judge -> validation 'unknown', diet not regenerated",
          (result.get("task_validation") or {}).get("diet", {}).get("status") == "unknown"
          and SCRIPT["diet_calls"] == 1 and result.get("replan_count") == 0, result.get("task_validation"))
    check("U: status needs_review, goal not completed, diet still shown",
          result.get("final_status") == "needs_review" and honest(result)
          and "Nutrition Plan" in (result.get("final_report") or ""), result.get("final_status"))

    # In a full plan, UNKNOWN on diet does not touch workout/gym.
    _reset_script()
    profile = UserProfileData(**full_profile())
    SCRIPT["diet_good_totals"] = compute_macro_target(profile, FULL_QUERY)
    SCRIPT["judge_outputs"] = ["not json at all"]
    _, config = new_session({**full_profile(), "location": "Mohali"})
    result = _with_fake_gym(lambda: send_turn(config, FULL_QUERY, FULL_TASKS))
    check("U: full plan - no task regenerated because the judge failed",
          SCRIPT["diet_calls"] == 1 and SCRIPT["workout_calls"] == 1 and result.get("replan_count") == 0,
          (SCRIPT["diet_calls"], SCRIPT["workout_calls"]))


# --- B2: best result preserved when a retry is worse ---
def test_b2_best_result_preservation():
    from agents.common import update_best
    best = {}
    update_best(best, "diet", "t1", {"diet_plan": "A"}, "validated")
    update_best(best, "diet", "t2", {"diet_plan": "B"}, "failed")
    update_best(best, "diet", "t3", {"diet_plan": "C"}, "unknown")
    check("B2: a failed/unknown attempt never replaces a validated one", best["diet"]["result"]["diet_plan"] == "A", best)
    best = {}
    update_best(best, "diet", "t1", {"diet_plan": "A"}, "failed")
    update_best(best, "diet", "t2", {"diet_plan": "B"}, "validated")
    check("B2: a validated attempt replaces a failed one", best["diet"]["result"]["diet_plan"] == "B", best)

    # Graph: attempt 1 has content but misses the cost line; attempt 2 is empty.
    _reset_script()
    attempt_1 = PUNJABI_DIET.replace("**Estimated Daily Cost:** ~₹120\n", "")
    SCRIPT["diet_outputs"] = [attempt_1, "", ""]
    _, config = new_session(full_profile())
    result = send_turn(config, PUNJABI_QUERY, [{"action": "diet", "depends_on": []}])
    report = result.get("final_report") or ""
    check("B2: empty retries never erase attempt 1 (report + session channel keep it)",
          "rajma chawal" in report and result.get("diet_plan") == attempt_1, report[:300])
    check("B2: unresolved diet -> incomplete, honest note", result.get("final_status") == "incomplete" and honest(result),
          result.get("final_status"))


RATE_LIMIT = Exception("Error code: 429 - {'error': {'message': 'Rate limit reached ... tokens per minute (TPM)', "
                       "'code': 'rate_limit_exceeded'}}")


# --- W: 429 stops the turn cleanly; no more agentic work ---
def test_w_rate_limit():
    tasks = [
        {"action": "bmi", "depends_on": []},
        {"action": "macros", "depends_on": ["bmi"]},
        {"action": "diet", "depends_on": ["macros"]},
        {"action": "workout", "depends_on": []},
    ]
    _reset_script()
    SCRIPT["raise_for"] = {"diet": RATE_LIMIT}
    SCRIPT["executor_choice"] = lambda text, options: options[0]  # diet first
    _, config = new_session(full_profile())
    result = send_turn(config, "Full plan please.", tasks)
    check("W1: 429 in diet -> final_status rate_limited, no success claimed",
          result.get("final_status") == "rate_limited" and honest(result), result.get("final_status"))
    check("W1: 429 did not trigger evaluator LLM, replanner, retries or more generation",
          SCRIPT["judge_calls"] == 0 and SCRIPT["replan_calls"] == 0 and result.get("replan_count") == 0
          and SCRIPT["workout_calls"] == 0 and len(events(result, "failed")) == 0,
          (SCRIPT["judge_calls"], SCRIPT["replan_calls"], SCRIPT["workout_calls"]))
    report = result.get("final_report") or ""
    check("W1: completed numbers preserved and rate limit explained",
          "Your Numbers" in report and "rate limit" in report.lower(), report[-300:])

    _reset_script()
    SCRIPT["raise_for"] = {"planner": RATE_LIMIT}
    _, config = new_session(full_profile())
    result = send_turn(config, "Full plan please.", tasks)
    check("W2: 429 in planner -> clean rate_limited turn, nothing executed",
          result.get("final_status") == "rate_limited" and executed(result) == [] and honest(result),
          result.get("final_status"))

    _reset_script()
    SCRIPT["diet_outputs"] = [PUNJABI_DIET]
    SCRIPT["raise_for"] = {"judge": RATE_LIMIT}
    _, config = new_session(full_profile())
    result = send_turn(config, PUNJABI_QUERY, [{"action": "diet", "depends_on": []}])
    check("W3: 429 in the judge -> diet kept as unverified, turn stops",
          result.get("final_status") == "rate_limited" and SCRIPT["diet_calls"] == 1
          and "rajma chawal" in (result.get("final_report") or ""), result.get("final_status"))


# --- X: per-turn LLM budget fails safely ---
def test_x_llm_budget():
    _reset_script()
    original = settings.MAX_LLM_CALLS_PER_TURN
    settings.MAX_LLM_CALLS_PER_TURN = 3
    try:
        _, config = new_session({**full_profile(), "location": "Mohali"})
        result = _with_fake_gym(lambda: send_turn(config, FULL_QUERY, FULL_TASKS))
    finally:
        settings.MAX_LLM_CALLS_PER_TURN = original
    check("X: budget reached -> status budget_exhausted, never more than the cap",
          result.get("final_status") == "budget_exhausted" and SCRIPT["llm_calls"] == 3
          and result.get("llm_calls") == 3 and honest(result), (result.get("final_status"), SCRIPT["llm_calls"]))
    check("X: deterministic results still reported", "Your Numbers" in (result.get("final_report") or ""))


# --- S: MAX_EXECUTION_STEPS stops the loop safely ---
def test_s_step_limit():
    _reset_script()
    original = settings.MAX_EXECUTION_STEPS
    settings.MAX_EXECUTION_STEPS = 2
    try:
        _, config = new_session(full_profile())
        result = send_turn(config, "BMI, water and macros please.", [
            {"action": "bmi", "depends_on": []},
            {"action": "water", "depends_on": []},
            {"action": "macros", "depends_on": []},
        ])
    finally:
        settings.MAX_EXECUTION_STEPS = original
    check("S: only MAX_EXECUTION_STEPS tasks ran", len(executed(result)) == 2, executed(result))
    check("S: step limit -> incomplete, not success",
          result.get("final_status") == "incomplete" and result.get("goal_completed") is False, result.get("evaluation"))
    check("S: no replan attempted after step cap", result.get("replan_count", 0) == 0)


# --- L: missing profile -> needs_input (tool not even executed) ---
def test_l_tool_failure_missing_profile():
    _reset_script()
    _, config = new_session({})  # no profile data at all
    result = send_turn(config, "Calculate my BMI.", [{"action": "bmi", "depends_on": []}])
    check("L: goal_completed False", result.get("goal_completed") is False)
    check("L: final_status needs_input", result.get("final_status") == "needs_input", result.get("evaluation"))
    check("L: bmi not executed with missing data", executed(result) == [], executed(result))
    check("L: no wasted replan", result.get("replan_count", 0) == 0)
    check("L: final_report carries a clarifying note", "weight" in (result.get("final_report") or "").lower())


# --- V: plan validation ---
def test_v_plan_validation():
    names = get_all_tool_names()
    base = {"type": "tool", "status": "pending"}
    check("V: valid plan passes", validate_plan([
        {**base, "id": "t1", "action": "bmi", "depends_on": []},
        {**base, "id": "t2", "action": "macros", "depends_on": ["t1"]},
    ], names) == [])
    check("V: unknown action rejected", validate_plan([{**base, "id": "t1", "action": "yoga", "depends_on": []}], names))
    check("V: self dependency rejected", validate_plan([{**base, "id": "t1", "action": "bmi", "depends_on": ["t1"]}], names))
    check("V: unresolved dependency rejected",
          validate_plan([{**base, "id": "t1", "action": "bmi", "depends_on": ["t9"]}], names))
    check("V: cycle rejected", any("cycle" in e.lower() for e in validate_plan([
        {**base, "id": "t1", "action": "bmi", "depends_on": ["t2"]},
        {**base, "id": "t2", "action": "macros", "depends_on": ["t1"]},
    ], names)))
    check("V: duplicate ids rejected", validate_plan([
        {**base, "id": "t1", "action": "bmi", "depends_on": []},
        {**base, "id": "t1", "action": "water", "depends_on": []},
    ], names))

    # Planner: invalid once -> repaired on second call.
    _reset_script()
    SCRIPT["planner_raw"] = [json.dumps({"goal": "g", "tasks": [{"action": "macros", "depends_on": ["bmi"]}]})]
    _, config = new_session(full_profile())
    result = send_turn(config, "My macros please.", [{"action": "macros", "depends_on": []}])
    check("V: planner repaired an unresolved dependency with one retry",
          SCRIPT["planner_calls"] == 2 and executed(result) == ["macros"]
          and result.get("final_status") == "success", (SCRIPT["planner_calls"], executed(result)))

    # Planner: invalid twice -> general fallback, never reported as success.
    _reset_script()
    SCRIPT["planner_raw"] = [
        json.dumps({"tasks": [{"action": "diet", "depends_on": ["diet"]}]}),
        json.dumps({"tasks": [{"action": "teleport", "depends_on": []}]}),
    ]
    _, config = new_session(full_profile())
    result = send_turn(config, "Diet plan please.", [])
    check("V: invalid plan is not executed (general fallback only)", executed(result) == ["general"], executed(result))
    check("V: fallback is recorded and status is incomplete",
          bool(events(result, "plan_invalid")) and result.get("final_status") == "incomplete", result.get("final_status"))


# --- H: profile update affects future turns ---
def test_h_profile_update_used():
    import asyncio
    from api.routes import update_profile
    from schemas.schemas import ProfileUpdateRequest

    _reset_script()
    session_id, config = new_session({})
    result = send_turn(config, "Calculate my BMI.", [{"action": "bmi", "depends_on": []}])
    check("H: first turn (no profile) needs input", result.get("final_status") == "needs_input")

    asyncio.run(update_profile(session_id, ProfileUpdateRequest(**full_profile())))
    result2 = send_turn(config, "Calculate my BMI.", [{"action": "bmi", "depends_on": []}])
    check("H: second turn succeeds using the updated profile", result2.get("final_status") == "success")
    bmi_before = result2["tool_results"]["bmi"]["bmi_data"]["bmi_value"]

    asyncio.run(update_profile(session_id, ProfileUpdateRequest(weight_kg=95)))
    check("H: profile change invalidates stale derived numbers",
          app_graph.get_state(config).values.get("bmi_data") is None)
    result3 = send_turn(config, "Calculate my BMI.", [{"action": "bmi", "depends_on": []}])
    bmi_after = result3["tool_results"]["bmi"]["bmi_data"]["bmi_value"]
    check("H: new weight used, other fields kept", bmi_after > bmi_before
          and result3["user_profile"].height_cm == 175, (bmi_before, bmi_after))


# --- I/J/T: session continuity, isolation, current-turn results ---
def test_i_j_session_continuity_and_isolation():
    _reset_script()
    _, config_a = new_session(full_profile())
    send_turn(config_a, "Calculate my BMI.", [{"action": "bmi", "depends_on": []}])
    state_a = app_graph.get_state(config_a).values
    check("I: session A's bmi_data persists in its own checkpoint", state_a.get("bmi_data") is not None)

    result = send_turn(config_a, "hi", [{"action": "general", "depends_on": []}])
    check("I: same session restores profile + history",
          result["user_profile"].weight_kg == 80 and len(result.get("messages") or []) == 4,
          len(result.get("messages") or []))
    check("T: old bmi kept as session context but not in the new turn's answer",
          result.get("bmi_data") is not None and "BMI" not in (result.get("final_report") or "")
          and "bmi" not in (result.get("tool_results") or {}), result.get("final_report"))

    _, config_b = new_session({})
    state_b = app_graph.get_state(config_b).values
    check("J: a different session_id starts isolated",
          state_b.get("bmi_data") is None and state_b.get("messages") == [] and state_b["user_profile"].weight_kg is None)


# --- K: existing tools still work ---
def test_k_existing_tools():
    from tools.bmi_tool import BMICalculatorTool
    from tools.water_tool import WaterCalculatorTool
    from tools.macro_tool import MacroCalculatorTool
    from tools.gym_finder import GymFinderTool

    profile = UserProfileData(**full_profile(), location="Mohali")
    state = {"user_profile": profile, "user_query": "lose fat", "messages": []}
    bmi = BMICalculatorTool.calculate(state)["bmi_data"]
    check("K: BMI tool", bmi["bmi_value"] == 26.12 and bmi["bmr"] == 1758.75, bmi)
    check("K: water tool", WaterCalculatorTool.calculate(state)["water_data"]["water_intake_liters"] == 3.55)
    macros = MacroCalculatorTool.calculate({**state, "bmi_data": bmi})["macro_data"]
    check("K: macro tool", macros["protein_g"] == 160 and round(macros["daily_calories_target"]) == round(1758.75 * 1.55 - 500),
          macros)
    check("K: diet tool", "Daily Totals" in diet_module.DietGeneratorTool.generate_diet(state)["diet_plan"])
    check("K: workout tool", "Squats" in workout_module.WorkoutGeneratorTool.generate_workout(state)["workout_plan"])
    check("K: general tool", general_module.GeneralFitnessTool.respond(state)["general_response"])
    original_key = settings.GEOAPIFY_API_KEY
    settings.GEOAPIFY_API_KEY = ""
    try:
        check("K: gym tool handles missing API key", "Geoapify" in GymFinderTool.find_gyms(state)["gym_data"])
    finally:
        settings.GEOAPIFY_API_KEY = original_key


# --- API: endpoints, SSE, old endpoints gone ---
def test_api_endpoints_and_sse():
    import asyncio
    asyncio.run(_api_checks())


async def _api_checks():
    # starlette 0.36's TestClient is incompatible with the installed httpx
    # 0.28, so drive the ASGI app through httpx directly.
    import httpx
    from main import app

    _reset_script()
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    check("API: GET /health", (await client.get("/health")).json() == {"status": "healthy"})

    created = (await client.post("/api/v1/sessions", json={"profile": {"weight_kg": 70}})).json()
    session_id = created["session_id"]
    check("API: POST /sessions creates a session", bool(session_id) and created["profile"]["weight_kg"] == 70)

    patched = (await client.patch(f"/api/v1/sessions/{session_id}/profile", json={
        "height_cm": 175, "age": 28, "gender": "male", "activity_level": "sedentary",
    })).json()
    check("API: PATCH profile merges fields", patched["profile"]["weight_kg"] == 70 and patched["profile"]["age"] == 28)

    SCRIPT["planner_tasks"] = [{"action": "bmi", "depends_on": []}]
    response = await client.post(f"/api/v1/sessions/{session_id}/chat/stream", json={"message": "my bmi?"})
    check("API: stream is text/event-stream", response.headers["content-type"].startswith("text/event-stream"))
    body = response.text
    names = re.findall(r"^event: (\w+)$", body, re.MULTILINE)
    done = json.loads(re.search(r"event: done\ndata: (.*)", body).group(1))
    check("API: SSE event sequence", names[0] == "start" and "planning" in names and "executing" in names
          and "evaluating" in names and names[-1] == "done", names)
    check("API: done carries honest status + this turn's data",
          done["status"] == "success" and done["goal_completed"] is True and done["bmi_data"]["bmi_value"] == 22.86, done)

    SCRIPT["planner_tasks"] = [{"action": "gym", "depends_on": []}]
    body = (await client.post(f"/api/v1/sessions/{session_id}/chat/stream", json={"message": "gyms near me"})).text
    done = json.loads(re.search(r"event: done\ndata: (.*)", body).group(1))
    check("API: missing location -> status needs_input, not success",
          done["status"] == "needs_input" and done["goal_completed"] is False and done["bmi_data"] is None, done)

    state = (await client.get(f"/api/v1/sessions/{session_id}/state")).json()
    check("API: GET state", state["final_status"] == "needs_input" and state["profile"]["age"] == 28)

    SCRIPT["planner_tasks"] = [{"action": "bmi", "depends_on": []}, {"action": "workout", "depends_on": []}]
    SCRIPT["raise_for"] = {"workout": RATE_LIMIT}
    body = (await client.post(f"/api/v1/sessions/{session_id}/chat/stream", json={"message": "bmi + workout"})).text
    SCRIPT["raise_for"] = {}
    names = re.findall(r"^event: (\w+)$", body, re.MULTILINE)
    done = json.loads(re.search(r"event: done\ndata: (.*)", body).group(1))
    check("API: 429 ends with a normal 'done' (status rate_limited), not an error event",
          "error" not in names and done["status"] == "rate_limited" and done["goal_completed"] is False
          and done["bmi_data"]["bmi_value"] == 22.86 and "rate limit" in done["final_report"].lower(), (names, done))

    check("API: DELETE session", (await client.delete(f"/api/v1/sessions/{session_id}")).status_code == 200)
    check("API: deleted session is gone", (await client.get(f"/api/v1/sessions/{session_id}/state")).status_code == 404)
    check("API: chat on unknown session 404s",
          (await client.post("/api/v1/sessions/nope/chat/stream", json={"message": "hi"})).status_code == 404)

    old = [
        (await client.post("/api/v1/generate-plan", json={})).status_code,
        (await client.post("/api/v1/generate-plan/stream", json={})).status_code,
        (await client.delete("/api/v1/clear-session/x")).status_code,
        (await client.post(f"/api/v1/sessions/{session_id}/chat", json={"message": "hi"})).status_code,
    ]
    check("API: old/non-streaming endpoints do not exist", all(code in (404, 405) for code in old), old)
    await client.aclose()


def main():
    tests = [
        test_a_simple_bmi,
        test_b_c_full_report_success,
        test_n_next_action_depends_on_result,
        test_d_e_replan_diet_only,
        test_r_structural_replan,
        test_f_second_replan_increments_version,
        test_g_repeated_failure_stops_early,
        test_g2_max_replan_protection,
        test_p_diet_only_constraints,
        test_q_full_plan_first_pass,
        test_t_full_plan_diet_retry,
        test_o_empty_and_truncated_output,
        test_u_evaluator_unknown,
        test_b2_best_result_preservation,
        test_w_rate_limit,
        test_x_llm_budget,
        test_s_step_limit,
        test_l_tool_failure_missing_profile,
        test_v_plan_validation,
        test_h_profile_update_used,
        test_i_j_session_continuity_and_isolation,
        test_k_existing_tools,
        test_api_endpoints_and_sse,
    ]
    for fn in tests:
        print(f"\n--- {fn.__name__} ---")
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            FAIL.append(fn.__name__)
            print(f"ERROR in {fn.__name__}: {exc!r}")
            import traceback
            traceback.print_exc()

    print(f"\n=== {len(PASS)} passed, {len(FAIL)} failed ===")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
