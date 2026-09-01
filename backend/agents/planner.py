import json
import re
from langchain_core.prompts import ChatPromptTemplate
from models.llm import get_llm
from graph.state import AgentState
from memory.session_memory import format_chat_history

# Importing the dynamic configuration APIs directly from our tools registry
from tools.registry import get_tools_metadata, get_all_tool_names


'''
                START
                  │
                  ▼
      Get User Query + Chat History from State
                  │
                  ▼
      state["user_query"] / state["user_profile"].query
      state["chat_history"]
                  │
                  ▼
         Load Available Tools
                  │
                  ▼
      get_tools_metadata()
      get_all_tool_names()
                  │
                  ▼
     Build Dynamic Tool List String
                  │
                  ▼
         Create Prompt Template
                  │
                  ▼
             Call LLM
                  │
                  ▼
          Extract JSON Block
                  │
                  ▼
              Return
                  │
                  ▼
      {
        "selected_tools": [...]
      }
                  │
                  ▼
                  END
'''


class PlannerAgent:
    """
    Dynamic routing engine that reads tool definitions from the Python registry,
    injects them dynamically into the system prompt, and parses the routing output safely.
    """

    @staticmethod
    def plan_execution(state: AgentState) -> dict:

        # 0.0 temperature for absolute consistency in logical tool classification
        llm = get_llm(temperature=0.0, purpose="router")

        # 1. Read current query + recent chat history
        current_query = state.get("user_query") or state["user_profile"].query
        formatted_history = format_chat_history(state.get("chat_history", []))

        # 2. Fetch metadata dynamically from tools package
        tools_catalog = get_tools_metadata()
        all_tool_names = get_all_tool_names()

        # 3. Compile dynamic instructions list
        formatted_tools_string = ""
        for tool in tools_catalog:
            formatted_tools_string += f"- '{tool['name']}': {tool['description']}\n"

        # 4. Build the system message string BEFORE passing to ChatPromptTemplate
        # This avoids LangChain treating {tools_catalog} as a variable
        system_message = (
            "You are an advanced orchestration routing engine for a fitness-only assistant.\n\n"
            "Your job is to decide which worker modules are needed for the CURRENT user message.\n\n"
            "Available modules:\n"
            f"{formatted_tools_string}\n"
            "Core decision rule:\n"
            "- The CURRENT user message has highest priority.\n"
            "- Conversation history is only for understanding context, references, and follow-ups.\n"
            "- Do NOT trigger plan generation, reports, or calculations just because they were discussed earlier in history.\n"
            "- Only select non-general tools if the CURRENT message explicitly asks for them.\n\n"
            "Select 'general' when:\n"
            "- the user says hi, hello, hey\n"
            "- the user asks a general fitness question\n"
            "- the user shares lifestyle/context/preferences such as: 'I am an office worker', 'I have less time', 'I am vegetarian', 'I have knee pain'\n"
            "- the user asks for general fitness advice\n"
            "- the user asks a non-fitness question that should be politely refused\n\n"
            "Select 'bmi' only when the user explicitly asks to calculate or know BMI/BMR.\n"
            "Select 'water' only when the user explicitly asks for water intake.\n"
            "Select 'macros' only when the user explicitly asks for calories/macros or asks for a full report.\n"
            "Select 'diet' only when the user explicitly asks to generate/create/build a diet plan, meal plan, or modify a previous diet plan.\n"
            "Select 'workout' only when the user explicitly asks to generate/create/build a workout plan, routine, schedule, or modify a previous workout plan.\n"
            "Select 'gym' only when the user explicitly asks for gym finding, gym setup guidance, or gym-related planning.\n\n"
            "Important:\n"
            "- If the user only shares new context or constraints, select only 'general'.\n"
            "- If the user explicitly asks to modify a previous generated workout or diet, you may select the relevant tool.\n"
            "- If the user asks for a full report, select all required report-generation tools.\n"
            "- If the user asks anything outside fitness, select only 'general' so the general node can politely refuse.\n"
            "- When in doubt, choose 'general', not generation.\n\n"
            "Examples:\n"
            "- 'hi' -> {{\"selected_tools\": [\"general\"]}}\n"
            "- 'hello, what is a good protein source?' -> {{\"selected_tools\": [\"general\"]}}\n"
            "- 'I am an office worker and have very little time' -> {{\"selected_tools\": [\"general\"]}}\n"
            "- 'generate a workout plan for me' -> {{\"selected_tools\": [\"workout\"]}}\n"
            "- 'make my previous workout shorter' -> {{\"selected_tools\": [\"workout\"]}}\n"
            "- 'create a vegetarian diet plan' -> {{\"selected_tools\": [\"diet\"]}}\n"
            "- 'calculate my bmi' -> {{\"selected_tools\": [\"bmi\"]}}\n"
            "- 'how much water should I drink?' -> {{\"selected_tools\": [\"water\"]}}\n"
            "- 'give me my calories and macros' -> {{\"selected_tools\": [\"macros\"]}}\n"
            "- 'generate my full fitness report' -> {{\"selected_tools\": [\"bmi\", \"water\", \"macros\", \"diet\", \"workout\", \"gym\"]}}\n"
            "- 'who is PM of India?' -> {{\"selected_tools\": [\"general\"]}}\n\n"
            "Return ONLY a valid JSON object with this exact format:\n"
            "{{\"selected_tools\": [\"general\"]}}\n\n"
            "Do not return markdown, explanations, notes, or code fences."
        )

        # 5. Create prompt template
        # Only {history} and {query} are LangChain variables now
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            ("user", (
                "Recent Conversation History:\n{history}\n\n"
                "Current User Message: '{query}'"
            ))
        ])

        chain = prompt | llm
        response = chain.invoke({
            "history": formatted_history,
            "query": current_query
        })

        cleaned_content = response.content.strip()

        # --------------------------------------------------
        #  Extract JSON block using regex
        # --------------------------------------------------
        json_match = re.search(r'\{.*?\}', cleaned_content, re.DOTALL)

        # Safe fallback:
        # If parsing fails, route to general instead of firing every tool.
        selected_tools = ["general"]

        if json_match:
            try:
                parsed_data = json.loads(json_match.group(0))
                raw_selected_tools = parsed_data.get("selected_tools", [])

                if isinstance(raw_selected_tools, list):
                    validated_tools = []

                    for tool_name in raw_selected_tools:
                        if tool_name in all_tool_names and tool_name not in validated_tools:
                            validated_tools.append(tool_name)

                    if validated_tools:
                        selected_tools = validated_tools

            except Exception:
                pass

        return {"selected_tools": selected_tools}