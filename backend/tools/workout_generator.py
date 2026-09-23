from langchain_core.prompts import ChatPromptTemplate

from graph.state import AgentState
from memory.session_memory import format_chat_history
from models.llm import call_llm, get_llm


class WorkoutGeneratorTool:
    """Generate a personalized workout response when the planner selects workout."""

    @staticmethod
    def generate_workout(state: AgentState) -> dict:
        llm = get_llm()
        profile = state["user_profile"]
        history = format_chat_history(state.get("messages", []))
        replan_feedback = state.get("replan_feedback") or "None"

        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert fitness coach specialized in personalized workout plans.

Respect the user's profile, activity level and constraints. Do not hallucinate personal details or medical conditions.
Keep the workout realistic, practical, structured and concise (under about 350 words)."""),
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
            "replan_feedback": replan_feedback,
        })

        return {"workout_plan": response.content}
