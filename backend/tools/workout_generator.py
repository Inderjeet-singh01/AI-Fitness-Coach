from langchain_core.prompts import ChatPromptTemplate

from graph.state import AgentState
from memory.session_memory import format_chat_history
from models.llm import get_llm


class WorkoutGeneratorTool:
    """Generate a personalized workout response when the planner selects workout."""

    @staticmethod
    def generate_workout(state: AgentState) -> dict:
        llm = get_llm()
        profile = state["user_profile"]
        history = format_chat_history(state.get("chat_history", []))

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert fitness coach specialized in personalized workout plans.

Generate a workout response ONLY when the CURRENT user message explicitly requests one.
Respect the user's profile, activity level and constraints. Do not hallucinate personal details or medical conditions.
Keep the workout realistic, practical, structured and concise."""),
            ("user", """Recent Conversation History:
{history}

User Profile:
- Age: {age}
- Gender: {gender}
- Weight: {weight} kg
- Height: {height} cm
- Activity Level: {activity_level}

Current User Message:
{query}"""),
        ])

        response = (prompt | llm).invoke({
            "history": history,
            "age": profile.age,
            "gender": profile.gender,
            "weight": profile.weight_kg,
            "height": profile.height_cm,
            "activity_level": profile.activity_level,
            "query": profile.query,
        })

        return {"workout_plan": response.content}
