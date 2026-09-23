from langchain_core.prompts import ChatPromptTemplate

from agents.constraints import describe_constraints
from graph.state import AgentState
from memory.session_memory import format_chat_history
from models.llm import call_llm, get_llm


class DietGeneratorTool:
    """Generate a personalized diet response when the planner selects diet."""

    @staticmethod
    def generate_diet(state: AgentState) -> dict:
        llm = get_llm()
        profile = state["user_profile"]
        history = format_chat_history(state.get("messages", []))
        # Only this turn's calculated numbers: earlier turns' targets may
        # belong to a different goal.
        results = state.get("tool_results") or {}
        macro_data = (results.get("macros") or {}).get("macro_data") or {}
        bmi_data = (results.get("bmi") or {}).get("bmi_data") or {}
        constraints = state.get("constraints") or {}

        replan_feedback = state.get("replan_feedback") or "None"

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert sports nutrition and fitness diet planning assistant.

Respect the user's profile, current goal, dietary preferences and the Explicit Constraints. Do not hallucinate personal details or medical conditions.
Keep the plan practical, realistic, structured and concise (under about 350 words). Use short Markdown headings, bullets, numbered lists, and blank lines. Do not use tables, dense paragraphs, or decorative separators.

If Macro Data is provided, the plan's meals must actually add up to the calorie target, and protein must be between protein_min_g and protein_g - do not ignore them.
If the constraints ask for a daily cost, add this line just before the totals: **Estimated Daily Cost:** ~<amount with currency symbol>
Always end the response with exactly one line in this format, with plain numbers (no ranges, no extra words):
**Daily Totals:** ~<calories> kcal | Protein: <protein>g | Carbs: <carbs>g | Fats: <fats>g"""),
            ("user", """Recent Conversation History:
{history}

User Profile:
- Age: {age}
- Gender: {gender}
- Weight: {weight} kg
- Height: {height} cm
- Activity Level: {activity_level}

Current User Message:
{query}

Explicit Constraints:
{constraints}

Available Calculated Context:
- Macro Data: {macro_data}
- BMI Data: {bmi_data}

Previous Attempt Issues To Fix (if any):
{replan_feedback}"""),
        ])

        response = call_llm(prompt | llm, {
            "history": history,
            "age": profile.age,
            "gender": profile.gender,
            "weight": profile.weight_kg,
            "height": profile.height_cm,
            "activity_level": profile.activity_level,
            "query": state.get("user_query") or "",
            "constraints": describe_constraints(constraints),
            "macro_data": macro_data,
            "bmi_data": bmi_data,
            "replan_feedback": replan_feedback,
        })

        return {"diet_plan": response.content}
