from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional, Any


# API Request Schema
class UserProfile(BaseModel):
    """
    Validates incoming user data from the API endpoint.
    """
    session_id: Optional[str] = Field(
        default=None,
        description="Temporary session identifier for RAM-based conversation memory"
    )

    weight_kg: float = Field(..., description="Weight in kilograms", gt=10, lt=300)
    height_cm: float = Field(..., description="Height in centimeters", gt=50, lt=250)
    gender: str = Field(..., description="Gender: male, female, or other")
    age: int = Field(..., description="Age in years", gt=1, lt=120)

    activity_level: str = Field(
        ...,
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
    query: str = Field(..., description="The user's specific text question or goal")

    @field_validator('gender')
    @classmethod
    def validate_gender(cls, value: str) -> str:
        cleaned_value = value.lower().strip()
        if cleaned_value not in ['male', 'female', 'other']:
            raise ValueError('Gender must be either male, female, or other')
        return cleaned_value

    @field_validator('activity_level')
    @classmethod
    def validate_activity_level(cls, value: str) -> str:
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


# API Response Schema
class FitnessBotResponse(BaseModel):
    status: str = "success"
    session_id: str
    bmi_data: Optional[Dict[str, Any]] = None
    water_data: Optional[Dict[str, Any]] = None
    macro_data: Optional[Dict[str, Any]] = None
    final_report: str