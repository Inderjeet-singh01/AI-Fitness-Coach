from graph.state import AgentState


def _section(title: str, body: str) -> str:
    body = (body or "").strip()
    return f"## {title}\n\n{body}" if body else ""


class AggregatorAgent:
    """Build a deterministic, consistently formatted final response.

    Only results produced by the CURRENT turn are used; session-level
    *_data left over from earlier turns never leak into an unrelated answer.
    For each task the best result of this turn is shown (best_results), so a
    failed retry can never blank out an earlier good attempt. Any status
    other than success always carries an explanatory note.
    """

    @staticmethod
    def compile_report(state: AgentState) -> dict:
        query = state.get("user_query") or ""
        plan = state.get("plan") or []
        results = state.get("tool_results") or {}
        evaluation = state.get("evaluation") or {}
        note = evaluation.get("user_message")

        best = state.get("best_results") or {}
        completed = {task["action"] for task in plan if task.get("status") == "completed"}
        final_status = state.get("final_status") or evaluation.get("status")
        if final_status != "success" and not note:
            note = "Some parts of this request could not be completed or verified."

        def turn_value(action: str, key: str):
            if action in best:
                return (best[action].get("result") or {}).get(key)
            return (results.get(action) or {}).get(key) if action in completed else None

        general = turn_value("general", "general_response")

        if [task["action"] for task in plan] == ["general"] and general and not note:
            report = general.strip()
            return {
                "final_report": report,
                "messages": [{"role": "assistant", "content": report}],
            }

        sections = []

        bmi = turn_value("bmi", "bmi_data")
        water = turn_value("water", "water_data")
        macros = turn_value("macros", "macro_data")
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

        diet_plan = turn_value("diet", "diet_plan")
        if diet_plan:
            sections.append(_section("Nutrition Plan", diet_plan))

        workout_plan = turn_value("workout", "workout_plan")
        if workout_plan:
            sections.append(_section("Workout Plan", workout_plan))

        gym_data = turn_value("gym", "gym_data")
        if gym_data:
            sections.append(_section("Nearby Gyms", gym_data))

        if general:
            sections.append(_section("Coach Guidance", general))

        if note:
            sections.append(_section("Note", note))

        if not sections:
            report = "I’m ready to help. Tell me what fitness goal you want to work on."
            return {
                "final_report": report,
                "messages": [{"role": "assistant", "content": report}],
            }

        intro = f"Here’s a focused response for: **{query}**."
        report = intro + "\n\n" + "\n\n".join(sections)
        return {
            "final_report": report,
            "messages": [{"role": "assistant", "content": report}],
        }
