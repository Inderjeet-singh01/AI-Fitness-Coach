from langchain_core.prompts import ChatPromptTemplate

from graph.state import AgentState
from memory.session_memory import format_chat_history
from models.llm import get_llm


class DietGeneratorTool:
    """Generate a personalized diet response when the planner selects diet."""

    @staticmethod
    def generate_diet(state: AgentState) -> dict:
        llm = get_llm()
        profile = state["user_profile"]
        history = format_chat_history(state.get("chat_history", []))
        macro_data = state.get("macro_data") or {}
        bmi_data = state.get("bmi_data") or {}

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert sports nutrition and fitness diet planning assistant.

Generate a diet response ONLY when the CURRENT user message explicitly requests one.
Respect the user's profile, current goal, dietary preferences and constraints. Do not hallucinate personal details or medical conditions.
Keep the plan practical, realistic, structured and concise. Use short Markdown headings, bullets, numbered lists, and blank lines. Do not use tables, dense paragraphs, or decorative separators."""),
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

Available Calculated Context:
- Macro Data: {macro_data}
- BMI Data: {bmi_data}"""),
        ])

        response = (prompt | llm).invoke({
            "history": history,
            "age": profile.age,
            "gender": profile.gender,
            "weight": profile.weight_kg,
            "height": profile.height_cm,
            "activity_level": profile.activity_level,
            "query": profile.query,
            "macro_data": macro_data,
            "bmi_data": bmi_data,
        })

        return {"diet_plan": response.content}
