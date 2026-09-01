from typing import TypedDict, List, Dict, Any, Optional
from schemas.schemas import UserProfile


class AgentState(TypedDict):
    user_profile: UserProfile
    session_id: Optional[str]
    user_query: str

    # Temporary Session-Based Conversation Memory
    chat_history: List[Dict[str, str]]

    selected_tools: List[str]

    # Dynamically Populated Tool Data
    bmi_data: Optional[Dict[str, Any]]
    water_data: Optional[Dict[str, Any]]
    macro_data: Optional[Dict[str, Any]]

    diet_plan: Optional[str]
    workout_plan: Optional[str]
    gym_data: Optional[str]

    # General Conversational Output
    general_response: Optional[str]

    retry_count: int
    current_errors: List[str]
    final_report: Optional[str]