# tools/water_tool.py
from graph.state import AgentState

class WaterCalculatorTool:
    @staticmethod
    def calculate(state: AgentState) -> dict:
        profile = state["user_profile"]
        
        base_liters = (profile.weight_kg * 35) / 1000
        if profile.activity_level in ["moderately_active", "very_active"]:
            base_liters += 0.75

        return {"water_data": {"water_intake_liters": round(base_liters, 2)}}