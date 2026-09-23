from typing import Any, Dict, List


"""
Dynamic Tools Registry:
Single source of truth for all planner-routable capabilities. The planner
reads `name`/`description` to build its prompt; the executor/graph read
`state_key` (where a capability's result lives in AgentState) and `node`
(which graph node runs it) and `requires` (profile fields the capability
cannot run without) so that execution order is driven by the plan,
not by a hardcoded mapping duplicated across modules.
"""


TOOLS_METADATA: List[Dict[str, Any]] = [
    {
        "name": "bmi",
        "description": "Calculate BMI value and BMR from the user's body profile.",
        "type": "tool",
        "state_key": "bmi_data",
        "node": "bmi_worker",
        "requires": ["weight_kg", "height_cm", "age", "gender"],
    },
    {
        "name": "water",
        "description": "Calculate daily water intake target based on body weight and activity level.",
        "type": "tool",
        "state_key": "water_data",
        "node": "water_worker",
        "requires": ["weight_kg"],
    },
    {
        "name": "macros",
        "description": "Calculate daily calorie and macronutrient targets aligned to the user's goal.",
        "type": "tool",
        "state_key": "macro_data",
        "node": "macros_worker",
        "requires": ["weight_kg", "height_cm", "age", "gender", "activity_level"],
    },
    {
        "name": "diet",
        "description": "Generate a personalized diet plan aligned to the user's goal and profile.",
        "type": "agent",
        "state_key": "diet_plan",
        "node": "diet_worker",
        "requires": [],
    },
    {
        "name": "workout",
        "description": "Generate a personalized workout plan aligned to the user's goal and profile.",
        "type": "agent",
        "state_key": "workout_plan",
        "node": "workout_worker",
        "requires": [],
    },
    {
        "name": "gym",
        "description": "Find nearby gyms using the user's city/area and provide gym setup or local fitness environment guidance.",
        "type": "agent",
        "state_key": "gym_data",
        "node": "gym_worker",
        "requires": ["location"],
    },
    {
        "name": "general",
        "description": "Handle greetings, general fitness conversation, fitness Q&A, and politely refuse non-fitness questions.",
        "type": "agent",
        "state_key": "general_response",
        "node": "general_worker",
        "requires": [],
    },
]


def get_tools_metadata() -> List[Dict[str, Any]]:
    return TOOLS_METADATA


def get_all_tool_names() -> List[str]:
    return [tool["name"] for tool in TOOLS_METADATA]


def get_state_key_map() -> Dict[str, str]:
    return {tool["name"]: tool["state_key"] for tool in TOOLS_METADATA}


def get_node_map() -> Dict[str, str]:
    return {tool["name"]: tool["node"] for tool in TOOLS_METADATA}


def get_type_map() -> Dict[str, str]:
    return {tool["name"]: tool["type"] for tool in TOOLS_METADATA}


def get_requirements_map() -> Dict[str, List[str]]:
    return {tool["name"]: list(tool.get("requires") or []) for tool in TOOLS_METADATA}
