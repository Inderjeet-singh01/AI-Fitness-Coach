from langchain_core.prompts import ChatPromptTemplate
from graph.state import AgentState
from models.llm import call_llm, get_llm
from memory.session_memory import format_chat_history


'''
                START
                  │
                  ▼
        Get Current Query + Chat History
                  │
                  ▼
     state["user_query"] / state["user_profile"].query
     state["messages"]
                  │
                  ▼
        Format Previous Conversation
                  │
                  ▼
        Build Fitness-Only Prompt
                  │
                  ▼
              Call LLM
                  │
                  ▼
        Generate General Response
                  │
                  ▼
     - Greeting if user says hi/hello
     - Fitness answer if query is fitness-related
     - Refusal if query is out-of-domain
                  │
                  ▼
              Return
                  │
                  ▼
      {
        "general_response": "..."
      }
                  │
                  ▼
                 END
'''


class GeneralFitnessTool:
    """
    Handles:
    - Greetings / casual conversation
    - General fitness Q&A
    - Polite refusal for non-fitness questions
    """

    @staticmethod
    def respond(state: AgentState) -> dict:
        llm = get_llm(temperature=0.3, purpose="general")

        profile = state["user_profile"]
        query = state.get("user_query") or ""
        chat_history = format_chat_history(state.get("messages", []))

        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are a professional fitness-only conversational assistant.\n\n"
                "Your role:\n"
                "- respond naturally to greetings\n"
                "- answer only fitness-related conversational questions\n"
                "- acknowledge user context, preferences, and constraints\n"
                "- politely refuse non-fitness questions\n"
                "- maintain continuity using recent conversation history\n\n"
                "Strict boundaries:\n"
                "- Do NOT generate a full workout plan unless the user explicitly asks for one in the CURRENT message.\n"
                "- Do NOT generate a full diet plan unless the user explicitly asks for one in the CURRENT message.\n"
                "- Do NOT generate a report, macros, BMI, or water calculations unless the user explicitly asks for them in the CURRENT message.\n"
                "- If the user is only sharing context such as being busy, vegetarian, injured, or having low time, acknowledge it and say you can use it for future plans if needed.\n"
                "- If the user asks a non-fitness question, politely refuse and redirect them to fitness-related help.\n"
                "- Never hallucinate the user's name or any personal detail not provided.\n"
                "- Do not claim actions were completed if they were not.\n\n"
                "Response style:\n"
                "- natural, helpful, and concise\n"
                "- no unnecessary markdown headings\n"
                "- no long structured plans unless explicitly requested\n"
                "- conversational but professional\n"
                "- use short paragraphs and bullets only when helpful"
            )),
            ("user", (
                "Recent Conversation History:\n{history}\n\n"
                "User Profile:\n"
                "- Age: {age}\n"
                "- Gender: {gender}\n"
                "- Weight: {weight} kg\n"
                "- Height: {height} cm\n"
                "- Activity Level: {activity_level}\n\n"
                "Current User Message:\n{query}"
            ))
        ])

        chain = prompt | llm
        response = call_llm(chain, {
            "history": chat_history,
            "age": profile.age,
            "gender": profile.gender,
            "weight": profile.weight_kg,
            "height": profile.height_cm,
            "activity_level": profile.activity_level,
            "query": query
        })

        return {"general_response": (response.content or "").strip()}