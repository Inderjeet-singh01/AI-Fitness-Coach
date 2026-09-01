from langgraph.graph import StateGraph, END, START
from typing import List
from graph.state import AgentState

# Import dynamic tools
from tools.bmi_tool import BMICalculatorTool
from tools.water_tool import WaterCalculatorTool
from tools.macro_tool import MacroCalculatorTool
from tools.diet_generator import DietGeneratorTool
from tools.workout_generator import WorkoutGeneratorTool
from tools.gym_finder import GymFinderTool
from tools.general_tool import GeneralFitnessTool

# Import Agents
from agents.planner import PlannerAgent
from agents.aggregator import AggregatorAgent


# --- Node Wrappers ---
def planner_node(state: AgentState): return PlannerAgent.plan_execution(state)
def bmi_node(state: AgentState): return BMICalculatorTool.calculate(state)
def water_node(state: AgentState): return WaterCalculatorTool.calculate(state)
def macro_node(state: AgentState): return MacroCalculatorTool.calculate(state)
def diet_node(state: AgentState): return DietGeneratorTool.generate_diet(state)
def workout_node(state: AgentState): return WorkoutGeneratorTool.generate_workout(state)
def gym_node(state: AgentState): return GymFinderTool.find_gyms(state)
def general_node(state: AgentState): return GeneralFitnessTool.respond(state)
def aggregator_node(state: AgentState): return AggregatorAgent.compile_report(state)


"""
 --- Dynamic Safe Sequential Routing ---

Determines the next node in the execution flow.
Returns the next selected worker from selected tools or the supervisor.
"""
def get_next_node(selected_tools: List[str], current_tool: str) -> str:
    """
    Finds the next tool in the hierarchy to execute, preventing missing dependencies.
    """
    sequence = ["bmi", "water", "macros", "diet", "workout", "gym", "general"]

    if current_tool == "planner":
        start_idx = 0
    else:
        start_idx = sequence.index(current_tool) + 1

    for i in range(start_idx, len(sequence)):
        if sequence[i] in selected_tools:
            return f"{sequence[i]}_worker"

    return "aggregator"


# Router wrappers for LangGraph conditionals
def route_from_planner(state: AgentState): return get_next_node(state.get("selected_tools", []), "planner")
def route_from_bmi(state: AgentState): return get_next_node(state.get("selected_tools", []), "bmi")
def route_from_water(state: AgentState): return get_next_node(state.get("selected_tools", []), "water")
def route_from_macros(state: AgentState): return get_next_node(state.get("selected_tools", []), "macros")
def route_from_diet(state: AgentState): return get_next_node(state.get("selected_tools", []), "diet")
def route_from_workout(state: AgentState): return get_next_node(state.get("selected_tools", []), "workout")
def route_from_gym(state: AgentState): return get_next_node(state.get("selected_tools", []), "gym")


"""
Routes execution after supervisor review.
Returns 're_evaluate' if quality issues exist and retries remain,
otherwise proceeds to final report generation.
"""
def route_after_supervisor(state: AgentState):
    errors = state.get("current_errors", [])
    retries = state.get("retry_count", 0)
    if errors and retries < 2:
        return "re_evaluate"
    return "finalize"


# --- Workflow Graph Assembly ---
workflow = StateGraph(AgentState)

# 1. Add all nodes
workflow.add_node("planner", planner_node)
workflow.add_node("bmi_worker", bmi_node)
workflow.add_node("water_worker", water_node)
workflow.add_node("macros_worker", macro_node)
workflow.add_node("diet_worker", diet_node)
workflow.add_node("workout_worker", workout_node)
workflow.add_node("gym_worker", gym_node)
workflow.add_node("general_worker", general_node)
workflow.add_node("aggregator", aggregator_node)

# 2. Set Entry
workflow.add_edge(START, "planner")

# 3. Dynamic Sequential Edges
workflow.add_conditional_edges("planner", route_from_planner)
workflow.add_conditional_edges("bmi_worker", route_from_bmi)
workflow.add_conditional_edges("water_worker", route_from_water)
workflow.add_conditional_edges("macros_worker", route_from_macros)
workflow.add_conditional_edges("diet_worker", route_from_diet)
workflow.add_conditional_edges("workout_worker", route_from_workout)
workflow.add_conditional_edges("gym_worker", route_from_gym)
workflow.add_edge("general_worker", "aggregator")

workflow.add_edge("aggregator", END)

app_graph = workflow.compile()