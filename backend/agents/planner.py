from typing import Any, Dict, List, Tuple

from langchain_core.prompts import ChatPromptTemplate
from models.llm import TurnHalted, call_llm, get_llm
from graph.state import AgentState
from agents.constraints import extract_constraints
from memory.session_memory import format_chat_history

from tools.registry import get_tools_metadata, get_all_tool_names, get_type_map
from agents.common import extract_json_object, tasks_from_llm, validate_plan


'''
                START
                  │
                  ▼
      Get User Query + Chat History from State
                  │
                  ▼
         Load Available Capabilities
                  │
                  ▼
      get_tools_metadata() / get_all_tool_names()
                  │
                  ▼
     Ask the LLM for a structured plan:
     goal + success_criteria + ordered tasks
                  │
                  ▼
      Validate the plan (known actions, no
      duplicates/self/unresolved deps, no cycles);
      one repair call if invalid, else a recorded
      general-only fallback
                  │
                  ▼
              Return
                  │
                  ▼
      {
        "goal": "...",
        "success_criteria": [...],
        "plan": [{"id","action","type","status","depends_on"}, ...],
        "selected_tools": [...],   # derived, informational only
        "current_task": None,
        "completed_tasks": [],
        "failed_tasks": [],
        "action_history": [...],
        "tool_results": {},          # current-turn results only
        "execution_steps": 0,
        ...other per-turn counters reset...
      }
                  │
                  ▼
                 END

Execution order is NOT decided here. The executor (agents/executor.py)
decides the next action one step at a time from the latest state; this node only
decides WHAT is needed for the current message, not the fixed order it
must run in.
'''


class PlannerAgent:
    """
    Turns the current user message (+ recent history) into a structured,
    dynamically-sized plan built only from the capabilities in the tools
    registry. No fixed fitness sequence is hardcoded here — the LLM chooses
    which capabilities are relevant and how they relate to each other.
    """

    @staticmethod
    def plan_execution(state: AgentState) -> dict:
        llm = get_llm(temperature=0.0, purpose="router")

        current_query = state.get("user_query") or ""
        formatted_history = format_chat_history(state.get("messages", []))

        tools_catalog = get_tools_metadata()
        all_tool_names = get_all_tool_names()
        type_map = get_type_map()

        formatted_tools_string = ""
        for tool in tools_catalog:
            formatted_tools_string += f"- '{tool['name']}': {tool['description']}\n"

        system_message = (
            "You are an advanced planning engine for a fitness-only assistant.\n\n"
            "Given the user's CURRENT message, produce a structured plan made ONLY of the "
            "capabilities listed below. Do not invent capabilities that aren't listed.\n\n"
            "Available capabilities:\n"
            f"{formatted_tools_string}\n"
            "Core decision rule:\n"
            "- The CURRENT user message has highest priority.\n"
            "- Conversation history is only for understanding context, references, and follow-ups.\n"
            "- Do NOT plan a calculation, plan, or report just because it was discussed earlier in history.\n"
            "- Only include a non-general capability if the CURRENT message explicitly asks for it.\n\n"
            "Include 'general' when:\n"
            "- the user says hi, hello, hey\n"
            "- the user asks a general fitness question\n"
            "- the user shares lifestyle/context/preferences such as: 'I am an office worker', 'I have less time', 'I am vegetarian', 'I have knee pain'\n"
            "- the user asks for general fitness advice\n"
            "- the user asks a non-fitness question that should be politely refused\n\n"
            "Include 'bmi' only when the user explicitly asks to calculate or know BMI/BMR.\n"
            "Include 'water' only when the user explicitly asks for water intake.\n"
            "Include 'macros' only when the user explicitly asks for calories/macros or asks for a full report.\n"
            "Include 'diet' only when the user explicitly asks to generate/create/build a diet plan, meal plan, or modify a previous diet plan.\n"
            "Include 'workout' only when the user explicitly asks to generate/create/build a workout plan, routine, schedule, or modify a previous workout plan.\n"
            "Include 'gym' only when the user explicitly asks for gym finding, gym setup guidance, or gym-related planning.\n\n"
            "Important:\n"
            "- If the user only shares new context or constraints, plan only 'general'.\n"
            "- If the user explicitly asks to modify a previous generated workout or diet, you may plan the relevant capability.\n"
            "- If the user asks for a full report, plan all required report-generation capabilities.\n"
            "- If the user asks anything outside fitness, plan only 'general' so it can politely refuse.\n"
            "- When in doubt, plan 'general', not generation.\n\n"
            "Dependency guidance (use plain capability names, not ids):\n"
            "- If both 'macros' and 'diet' are planned, 'diet' should depend_on ['macros'] (for calorie targets).\n"
            "- If both 'bmi' and 'macros' are planned, 'macros' should depend_on ['bmi'] (for BMR).\n"
            "- Otherwise leave depends_on as an empty list.\n"
            "- Never make a capability depend on itself or on something not in the plan.\n\n"
            "goal: one short sentence describing what the user is trying to accomplish.\n"
            "success_criteria: 1-4 short bullet strings describing what 'done' looks like for this plan. "
            "Each must be objectively checkable from the output (e.g. 'Diet is vegetarian', "
            "'Diet states an estimated daily cost', 'Meals are mainly Punjabi dishes'); never vague "
            "wording such as 'diet is cheap' or 'plan is good'.\n\n"
            "Examples:\n"
            "- 'hi' -> {{\"goal\": \"Greet the user\", \"success_criteria\": [\"Respond warmly and briefly\"], \"tasks\": [{{\"action\": \"general\", \"depends_on\": []}}]}}\n"
            "- 'hello, what is a good protein source?' -> {{\"goal\": \"Answer a general nutrition question\", \"success_criteria\": [\"Answer is accurate and fitness-related\"], \"tasks\": [{{\"action\": \"general\", \"depends_on\": []}}]}}\n"
            "- 'I am an office worker and have very little time' -> {{\"goal\": \"Acknowledge the user's context\", \"success_criteria\": [\"Context is acknowledged, no plan generated\"], \"tasks\": [{{\"action\": \"general\", \"depends_on\": []}}]}}\n"
            "- 'generate a workout plan for me' -> {{\"goal\": \"Create a personalized workout plan\", \"success_criteria\": [\"Workout matches user goal/constraints\"], \"tasks\": [{{\"action\": \"workout\", \"depends_on\": []}}]}}\n"
            "- 'create a vegetarian diet plan' -> {{\"goal\": \"Create a personalized diet plan\", \"success_criteria\": [\"Diet respects stated preferences\"], \"tasks\": [{{\"action\": \"diet\", \"depends_on\": []}}]}}\n"
            "- 'calculate my bmi' -> {{\"goal\": \"Calculate the user's BMI\", \"success_criteria\": [\"BMI and status are reported\"], \"tasks\": [{{\"action\": \"bmi\", \"depends_on\": []}}]}}\n"
            "- 'give me my calories and macros' -> {{\"goal\": \"Calculate daily calorie and macro targets\", \"success_criteria\": [\"Calorie and macro targets are reported\"], \"tasks\": [{{\"action\": \"macros\", \"depends_on\": []}}]}}\n"
            "- 'generate my full fitness report' -> {{\"goal\": \"Create a personalized weight-management plan\", \"success_criteria\": [\"Required calculations completed\", \"Diet matches nutritional targets\", \"Workout matches user goal/constraints\"], \"tasks\": [{{\"action\": \"bmi\", \"depends_on\": []}}, {{\"action\": \"water\", \"depends_on\": []}}, {{\"action\": \"macros\", \"depends_on\": [\"bmi\"]}}, {{\"action\": \"diet\", \"depends_on\": [\"macros\"]}}, {{\"action\": \"workout\", \"depends_on\": []}}, {{\"action\": \"gym\", \"depends_on\": []}}]}}\n"
            "- 'who is PM of India?' -> {{\"goal\": \"Politely refuse an off-topic question\", \"success_criteria\": [\"User is redirected to fitness topics\"], \"tasks\": [{{\"action\": \"general\", \"depends_on\": []}}]}}\n\n"
            "Return ONLY a valid JSON object with this exact shape:\n"
            "{{\"goal\": \"...\", \"success_criteria\": [\"...\"], \"tasks\": [{{\"action\": \"general\", \"depends_on\": []}}]}}\n\n"
            "Do not return markdown, explanations, notes, or code fences."
        )

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", (
                "Recent Conversation History:\n{history}\n\n"
                "Current User Message: '{query}'"
            )),
            ("placeholder", "{repair}"),
        ])
        chain = prompt | llm
        inputs = {"history": formatted_history, "query": current_query, "repair": []}

        # One LLM call, plus at most one repair call if the plan fails
        # structural validation. An invalid plan is never executed.
        parsed, plan, errors = {}, [], []
        turn_halt = None
        try:
            for _attempt in range(2):
                content = (call_llm(chain, inputs).content or "").strip()
                parsed = extract_json_object(content) or {}
                plan, errors = PlannerAgent._build_plan(parsed.get("tasks"), all_tool_names, type_map)
                if not errors:
                    break
                inputs["repair"] = [
                    ("assistant", content[:1500]),
                    ("user", "That plan is invalid: " + " ".join(errors)
                     + " Return a corrected JSON object with the same shape only."),
                ]
        except TurnHalted as exc:
            # No plan could be made (rate limit / budget): stop the turn
            # cleanly instead of falling back to more LLM work.
            turn_halt = {"kind": exc.kind, "detail": str(exc)[:300], "action": "planner"}
            parsed, plan, errors = {}, [], []

        goal = parsed.get("goal")
        if not isinstance(goal, str) or not goal.strip():
            goal = f"Respond to the user's current request: {current_query}"[:200]

        success_criteria = parsed.get("success_criteria")
        if not isinstance(success_criteria, list) or not success_criteria:
            success_criteria = ["Response directly addresses the user's current message."]
        success_criteria = [str(item) for item in success_criteria if str(item).strip()][:6]

        action_history: List[Dict[str, Any]] = []
        if turn_halt:
            action_history.append({"event": "plan_halted", "reason": turn_halt["kind"]})
        elif errors:
            # Fall back to a conversational reply, but record why so the
            # evaluator cannot report this turn as a full success.
            action_history.append({"event": "plan_invalid", "errors": errors})
            plan = [{
                "id": "t1",
                "action": "general",
                "type": type_map.get("general", "agent"),
                "status": "pending",
                "depends_on": [],
            }]
        action_history.append({"event": "planned", "plan_version": 1, "task_count": len(plan)})

        selected_tools = []
        for task in plan:
            if task["action"] not in selected_tools:
                selected_tools.append(task["action"])

        # Everything below is per-turn: a new user message gets its own plan,
        # counters and results. Session context (user_profile, messages and
        # the last known *_data values) is left untouched in the checkpoint.
        return {
            "goal": goal,
            "success_criteria": success_criteria,
            "plan": plan,
            "plan_version": 1,
            "plan_errors": errors,
            "selected_tools": selected_tools,
            "current_task": None,
            "completed_tasks": [],
            "failed_tasks": [],
            "action_history": action_history,
            "tool_results": {},
            "last_observation": None,
            "current_errors": [],
            "execution_steps": 0,
            "next_action": None,
            "evaluation": None,
            "final_status": None,
            "final_report": None,
            "goal_completed": False,
            "replan_required": False,
            "replan_reason": None,
            "replan_count": 0,
            "replan_feedback": None,
            "task_validation": {},
            "best_results": {},
            "constraints": extract_constraints(current_query),
            "handoff_reason": None,
            "turn_halt": turn_halt,
        }

    @staticmethod
    def _build_plan(
        raw_tasks: Any,
        all_tool_names: List[str],
        type_map: Dict[str, str],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Convert the LLM's task list into plan tasks and validate it.

        Returns (plan, errors). A non-empty `errors` means the plan must not
        be executed: unknown actions, duplicates, self/unresolved
        dependencies and cycles are reported rather than silently repaired.
        """
        plan, errors = tasks_from_llm(raw_tasks, type_map)
        return plan, errors + validate_plan(plan, all_tool_names)
