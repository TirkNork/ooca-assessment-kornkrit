"""Assembles the triage StateGraph.

START → load_context → agent ⇄ tools → classify → (auto_respond | route_specialist |
escalate_human) → END
"""

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from triage.config import Settings
from triage.graph.nodes import TriageNodes, route_after_agent, route_by_action
from triage.graph.state import TriageState
from triage.models import Action
from triage.repositories import Repositories
from triage.tools import build_tools


def build_graph(
    llm: BaseChatModel, repositories: Repositories, settings: Settings
) -> CompiledStateGraph:
    tools = build_tools(repositories)
    nodes = TriageNodes(llm, tools, repositories.customers, settings.max_tool_iterations)

    graph = StateGraph(TriageState)
    graph.add_node("load_context", nodes.load_context)
    graph.add_node("agent", nodes.agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("classify", nodes.classify)
    action_nodes = {
        Action.AUTO_RESPOND: nodes.auto_respond,
        Action.ROUTE_SPECIALIST: nodes.route_specialist,
        Action.ESCALATE_HUMAN: nodes.escalate_human,
    }
    for action, node in action_nodes.items():
        graph.add_node(action.value, node)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "agent")
    graph.add_conditional_edges("agent", route_after_agent, ["tools", "classify"])
    graph.add_edge("tools", "agent")
    graph.add_conditional_edges("classify", route_by_action, [a.value for a in Action])
    for action in Action:
        graph.add_edge(action.value, END)

    return graph.compile()
