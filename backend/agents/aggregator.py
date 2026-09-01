from graph.state import AgentState


def _section(title: str, body: str) -> str:
    body = (body or "").strip()
    return f"## {title}\n\n{body}" if body else ""


class AggregatorAgent:
    """Build a deterministic, consistently formatted final response."""

    @staticmethod
    def compile_report(state: AgentState) -> dict:
        query = state.get("user_query") or state["user_profile"].query
        selected_tools = state.get("selected_tools", [])
        general = state.get("general_response")

        if selected_tools == ["general"] and general:
            return {"final_report": general.strip()}

        sections = []

        bmi = state.get("bmi_data")
        water = state.get("water_data")
        macros = state.get("macro_data")
        if bmi or water or macros:
            lines = []
            if bmi:
                lines.append(f"- **BMI:** {bmi.get('bmi_value', '—')} ({bmi.get('bmi_status', '—')})")
                lines.append(f"- **BMR:** {bmi.get('bmr', '—')} kcal/day")
            if macros:
                lines.append(f"- **Daily calories:** {macros.get('daily_calories_target', '—')} kcal/day")
                lines.append(f"- **Protein:** {macros.get('protein_g', '—')} g/day")
                lines.append(f"- **Carbohydrates:** {macros.get('carbs_g', '—')} g/day")
                lines.append(f"- **Fats:** {macros.get('fats_g', '—')} g/day")
            if water:
                lines.append(f"- **Water:** {water.get('water_intake_liters', '—')} L/day")
            sections.append(_section("Your Numbers", "\n".join(lines)))

        if state.get("diet_plan"):
            sections.append(_section("Nutrition Plan", state["diet_plan"]))

        if state.get("workout_plan"):
            sections.append(_section("Workout Plan", state["workout_plan"]))

        if state.get("gym_data"):
            sections.append(_section("Nearby Gyms", state["gym_data"]))

        if general and "general" in selected_tools:
            sections.append(_section("Coach Guidance", general))

        if not sections:
            return {"final_report": "I’m ready to help. Tell me what fitness goal you want to work on."}

        intro = f"Here’s a focused response for: **{query}**."
        return {"final_report": intro + "\n\n" + "\n\n".join(sections)}
