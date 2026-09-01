from langchain_core.prompts import ChatPromptTemplate
from graph.state import AgentState
from models.llm import get_llm

'''
                START
                  │
                  ▼
      Check retry_count >= 2 ?
                  │
        ┌─────────┴─────────┐
        │ Yes               │ No
        ▼                   ▼
 Return current_errors=[]   Load LLM
        │                   │
        ▼                   ▼
       END          Build Audit Prompt
                            │
                            ▼
                  Collect State Data
                            │
                            ▼
                  selected_tools
                  general_response
                  diet_plan
                  workout_plan
                  gym_data
                            │
                            ▼
                    LLM Audit Call
                            │
                            ▼
                 response.content
                            │
                            ▼
          verdict = response.content
                    .strip()
                    .upper()
                            │
                            ▼
              Contains "PASSED" ?
                            │
             ┌──────────────┴──────────────┐
             │ Yes                         │ No
             ▼                             ▼
      errors = []             Add error message
                                      │
                                      ▼
                     errors.append(
                       "Quality Check Failed..."
                     )
                                      │
                                      ▼
                           Increment retry_count
                                      │
                                      ▼
                               Return State
                                      │
                                      ▼
                                     END
'''


class SupervisorAgent:
    """
    Audits the generated textual plan variants from the worker nodes to ensure
    professional standards, domain restriction, and high-quality formatting.
    """

    @staticmethod
    def audit_quality(state: AgentState) -> dict:
        """
        Evaluates current worker outputs. Flags corrections or approves execution advancement.
        """

        # Avoid infinite loop, Return empty errors if loop reached limit=2
        if state.get("retry_count", 0) >= 2:
            return {"current_errors": []}

        llm = get_llm(temperature=0.1)

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an elite quality-control auditor for a fitness-only multi-agent system.\n\n"
                "Your task is to check whether the generated outputs match the CURRENT user message and respect tool boundaries.\n\n"
                "Audit priorities:\n"
                "1. The response must match the CURRENT user intent.\n"
                "2. If the CURRENT user message did NOT explicitly request a plan, report, or calculation, then structured generated outputs such as workout plans, diet plans, reports, or analytics should be flagged as inappropriate.\n"
                "3. If the user only shared context or constraints, a conversational acknowledgment or brief guidance is acceptable.\n"
                "4. If 'general' handled a non-fitness question, a polite refusal should PASS.\n"
                "5. If a plan was explicitly requested, it should be useful, structured, and aligned with user constraints.\n"
                "6. Flag hallucinated names, invented facts, or unsupported assumptions.\n"
                "7. Flag repetitive or duplicated content across sections.\n"
                "8. Ensure the response remains within the fitness domain.\n\n"
                "Pass conditions:\n"
                "- Respond exactly with: PASSED\n\n"
                "Fail conditions:\n"
                "- If anything is wrong, do NOT say PASSED.\n"
                "- Instead return a concise list of issues.\n\n"
                "Important:\n"
                "- Over-generation is a failure.\n"
                "- Wrong tool behavior is a failure.\n"
                "- Hallucinated personal details are a failure."
            )),
            ("user", (
                "Current User Message:\n{query}\n\n"
                "Selected Tools:\n{selected_tools}\n\n"
                "General Output:\n{general_response}\n\n"
                "Diet Output:\n{diet_plan}\n\n"
                "Workout Output:\n{workout_plan}\n\n"
                "Gym Output:\n{gym_data}"
            ))
        ])

        chain = prompt | llm
        response = chain.invoke({
            "query": state.get("user_query") or state["user_profile"].query,
            "selected_tools": ", ".join(state.get("selected_tools", [])),
            "general_response": state.get("general_response") or "N/A",
            "diet_plan": state.get("diet_plan") or "N/A",
            "workout_plan": state.get("workout_plan") or "N/A",
            "gym_data": state.get("gym_data") or "N/A"
        })

        verdict = response.content.strip().upper()
        errors = []

        if "PASSED" not in verdict:
            errors.append(f"Quality Check Failed: {response.content}")

        return {
            "current_errors": errors,
            "retry_count": state.get("retry_count", 0) + 1
        }