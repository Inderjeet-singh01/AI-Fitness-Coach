# tools/macro_tool.py
from graph.state import AgentState

class MacroCalculatorTool:
    @staticmethod
    def calculate(state: AgentState) -> dict:
        profile = state["user_profile"]
        
        # Reuse this turn's BMR if the BMI tool ran, else calculate it locally
        # (never a previous turn's value).
        bmi_data = ((state.get("tool_results") or {}).get("bmi") or {}).get("bmi_data")
        if bmi_data: bmr = bmi_data["bmr"]
        else:
            w, h, a, g = profile.weight_kg, profile.height_cm, profile.age, profile.gender
            if g == "male": bmr = (10 * w) + (6.25 * h) - (5 * a) + 5
            elif g == "female": bmr = (10 * w) + (6.25 * h) - (5 * a) - 161
            else: bmr = (10 * w) + (6.25 * h) - (5 * a) - 78
        
        # Calculate TDEE
        multipliers = {"sedentary": 1.2, "lightly_active": 1.375, "moderately_active": 1.55, "very_active": 1.725}
        tdee = bmr * multipliers.get(profile.activity_level, 1.2)

        # Apply Goals
        query_lower = (state.get("user_query") or "").lower()
        if any(w in query_lower for w in ["lose", "fat loss", "weight loss", "cutting", "lean"]): target = tdee - 500
        elif any(w in query_lower for w in ["gain", "muscle gain", "bulking", "mass"]): target = tdee + 300
        else: target = tdee
        
        # Calculate Macros (protein target 2.0 g/kg; 1.6 g/kg is the lowest
        # a generated diet may reach and still count as on target)
        protein_g = round(profile.weight_kg * 2.0)
        protein_min_g = round(profile.weight_kg * 1.6)
        fat_g = round((target * 0.25) / 9)
        carb_g = round(max((target - ((protein_g * 4) + (fat_g * 9))) / 4, 0))

        return {"macro_data": {
            "daily_calories_target": round(target, 2),
            "protein_g": protein_g, "protein_min_g": protein_min_g, "carbs_g": carb_g, "fats_g": fat_g
        }}