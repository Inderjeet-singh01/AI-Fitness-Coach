# tools/macro_tool.py
from graph.state import AgentState

class MacroCalculatorTool:
    @staticmethod
    def calculate(state: AgentState) -> dict:
        profile = state["user_profile"]
        
        # Calculate BMR locally if BMI tool wasn't selected
        if state.get("bmi_data"): bmr = state["bmi_data"]["bmr"]
        else:
            w, h, a, g = profile.weight_kg, profile.height_cm, profile.age, profile.gender
            if g == "male": bmr = (10 * w) + (6.25 * h) - (5 * a) + 5
            elif g == "female": bmr = (10 * w) + (6.25 * h) - (5 * a) - 161
            else: bmr = (10 * w) + (6.25 * h) - (5 * a) - 78
        
        # Calculate TDEE
        multipliers = {"sedentary": 1.2, "lightly_active": 1.375, "moderately_active": 1.55, "very_active": 1.725}
        tdee = bmr * multipliers.get(profile.activity_level, 1.2)

        # Apply Goals
        query_lower = profile.query.lower()
        if any(w in query_lower for w in ["lose", "fat loss", "weight loss", "cutting", "lean"]): target = tdee - 500
        elif any(w in query_lower for w in ["gain", "muscle gain", "bulking", "mass"]): target = tdee + 300
        else: target = tdee
        
        # Calculate Macros
        protein_g = round(profile.weight_kg * 2.0)
        fat_g = round((target * 0.25) / 9)
        carb_g = round(max((target - ((protein_g * 4) + (fat_g * 9))) / 4, 0))

        return {"macro_data": {
            "daily_calories_target": round(target, 2),
            "protein_g": protein_g, "carbs_g": carb_g, "fats_g": fat_g
        }}