from pydantic import BaseModel, Field, field_validator
from typing import Dict, List, Optional, Any


# --- User Profile (progressively supplied; lives in runtime session state) ---
class UserProfileData(BaseModel):
    """
    Body-metrics profile for a session. All fields are optional so that a
    session can be created before any profile data is known, and updated
    later via PATCH without requiring the full profile on every chat turn.
    """
    weight_kg: Optional[float] = Field(default=None, description="Weight in kilograms", gt=10, lt=300)
    height_cm: Optional[float] = Field(default=None, description="Height in centimeters", gt=50, lt=250)
    gender: Optional[str] = Field(default=None, description="Gender: male, female, or other")
    age: Optional[int] = Field(default=None, description="Age in years", gt=1, lt=120)

    activity_level: Optional[str] = Field(
        default=None,
        description="Activity level: sedentary, lightly_active, moderately_active, very_active"
    )
    # Optional Combined Location Field for Gym Finder
    # Example:
    # - "Kharar, Mohali"
    # - "Model Town, Lahore"
    # - "Delhi"
    location: Optional[str] = Field(
        default=None,
        description="Combined location string for nearby gym search"
    )

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned_value = value.lower().strip()
        if cleaned_value not in ['male', 'female', 'other']:
            raise ValueError('Gender must be either male, female, or other')
        return cleaned_value

    @field_validator('activity_level')
    @classmethod
    def validate_activity_level(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        allowed_levels = ['sedentary', 'lightly_active', 'moderately_active', 'very_active']
        cleaned_value = value.lower().strip()
        if cleaned_value not in allowed_levels:
            raise ValueError(f'Activity level must be one of {allowed_levels}')
        return cleaned_value

    @field_validator('location')
    @classmethod
    def validate_location(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            cleaned = value.strip()
            if len(cleaned) < 2:
                raise ValueError('Location must be at least 2 characters long')
            return cleaned
        return value


# --- Session lifecycle schemas ---
class SessionCreateRequest(BaseModel):
    """Optional initial profile data when opening a session."""
    profile: Optional[UserProfileData] = None


class SessionCreateResponse(BaseModel):
    session_id: str
    profile: UserProfileData


class ProfileUpdateRequest(UserProfileData):
    """PATCH body: only supplied fields are merged into the existing profile."""
    pass


class ChatMessageRequest(BaseModel):
    """Body for a chat turn. Profile data is NOT required here; it lives in session state."""
    message: str = Field(..., description="The user's current chat message")


class SessionStateResponse(BaseModel):
    """Development/debugging view of a session's current runtime state."""
    session_id: str
    profile: UserProfileData
    selected_tools: List[str] = []
    bmi_data: Optional[Dict[str, Any]] = None
    water_data: Optional[Dict[str, Any]] = None
    macro_data: Optional[Dict[str, Any]] = None
    diet_plan: Optional[str] = None
    workout_plan: Optional[str] = None
    gym_data: Optional[str] = None
    general_response: Optional[str] = None
    final_report: Optional[str] = None
    # Plan + execution loop, exposed for debugging/testing.
    goal: Optional[str] = None
    success_criteria: Optional[List[str]] = None
    plan: Optional[List[Dict[str, Any]]] = None
    completed_tasks: List[Dict[str, Any]] = []
    failed_tasks: List[Dict[str, Any]] = []
    action_history: List[Dict[str, Any]] = []
    # Evaluator/replanner loop, exposed for debugging/testing.
    plan_version: int = 0
    goal_completed: bool = False
    final_status: Optional[str] = None
    tool_results: Dict[str, Any] = {}
    replan_count: int = 0
    evaluation: Optional[Dict[str, Any]] = None
    # Task-level validation and per-turn LLM usage, exposed for debugging.
    task_validation: Dict[str, Any] = {}
    constraints: Dict[str, Any] = {}
    llm_calls: int = 0
    llm_tokens: int = 0


# --- API Response Schema (SSE "done" payload) ---
class FitnessBotResponse(BaseModel):
    # success | needs_input | needs_review | incomplete | rate_limited |
    # budget_exhausted | error
    status: str
    session_id: str
    bmi_data: Optional[Dict[str, Any]] = None
    water_data: Optional[Dict[str, Any]] = None
    macro_data: Optional[Dict[str, Any]] = None
    final_report: str
