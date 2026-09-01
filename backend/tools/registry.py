from typing import List, Dict


"""
Dynamic Tools Registry:
Single source of truth for all planner-routable tools.
"""


TOOLS_METADATA: List[Dict[str, str]] = [
    {
        "name": "bmi",
        "description": "Calculate BMI value and BMR from the user's body profile."
    },
    {
        "name": "water",
        "description": "Calculate daily water intake target based on body weight and activity level."
    },
    {
        "name": "macros",
        "description": "Calculate daily calorie and macronutrient targets aligned to the user's goal."
    },
    {
        "name": "diet",
        "description": "Generate a personalized diet plan aligned to the user's goal and profile."
    },
    {
        "name": "workout",
        "description": "Generate a personalized workout plan aligned to the user's goal and profile."
    },
    {
        "name": "gym",
        "description": "Find nearby gyms using the user's city/area and provide gym setup or local fitness environment guidance."
    },
    {
        "name": "general",
        "description": "Handle greetings, general fitness conversation, fitness Q&A, and politely refuse non-fitness questions."
    }
]


def get_tools_metadata() -> List[Dict[str, str]]:
    return TOOLS_METADATA


def get_all_tool_names() -> List[str]:
    return [tool["name"] for tool in TOOLS_METADATA]