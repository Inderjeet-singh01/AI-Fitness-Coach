# tools/bmi_tool.py
from graph.state import AgentState

class BMICalculatorTool:
    @staticmethod
    def calculate(state: AgentState) -> dict:
        profile = state["user_profile"]
        
        weight, height, age, gender = profile.weight_kg, profile.height_cm, profile.age, profile.gender

        # Calculate BMI
        bmi_value = round(weight / ((height / 100) ** 2), 2)
        if bmi_value < 18.5: status = "Underweight"
        elif 18.5 <= bmi_value < 24.9: status = "Normal Weight"
        elif 25.0 <= bmi_value < 29.9: status = "Overweight"
        else: status = "Obese"

        # Calculate BMR (Mifflin-St Jeor)
        if gender == "male": bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        elif gender == "female": bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
        else: bmr = (10 * weight) + (6.25 * height) - (5 * age) - 78

        return {"bmi_data": {"bmi_value": bmi_value, "bmi_status": status, "bmr": round(bmr, 2)}}