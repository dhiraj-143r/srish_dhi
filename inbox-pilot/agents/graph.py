"""
InboxPilot — LangGraph Pipeline Definition
Builds the multi-agent graph with conditional routing based on triage output.
"""
import logging
import time
from langgraph.graph import StateGraph, START, END
from agents.state import EmailState
from agents.watcher import watcher_agent
from agents.triage import triage_agent
from agents.researcher import researcher_agent
from agents.vision import vision_agent
from agents.drafter import drafter_agent
from agents.action import action_agent

logger = logging.getLogger("inbox-pilot.graph")


def route_after_triage(state: EmailState) -> list[str]:
    """
    Conditional routing after triage.
    Determines which agents to run based on triage results.
    """
    needs_research = state.get("needs_research", False)
    has_attachments = state.get("has_attachments", False)
    action_type = state.get("action_type", "reply")

    # If archive, skip research/vision/drafting — go straight to action
    if action_type == "archive":
        return ["drafter"]  # Drafter will skip, then action runs

    destinations = []
    if needs_research:
        destinations.append("researcher")
    if has_attachments:
        destinations.append("vision")
    
    # If neither research nor vision needed, go to drafter
    if not destinations:
        destinations.append("drafter")
    
    return destinations


def build_graph() -> StateGraph:
    """Build the InboxPilot LangGraph pipeline."""
    
    graph = StateGraph(EmailState)
    
    # Add all agent nodes
    graph.add_node("watcher", watcher_agent)
    graph.add_node("triage", triage_agent)
    graph.add_node("researcher", researcher_agent)
    graph.add_node("vision", vision_agent)
    graph.add_node("drafter", drafter_agent)
    graph.add_node("action", action_agent)
    
    # Define edges
    # START → Watcher → Triage
    graph.add_edge(START, "watcher")
    graph.add_edge("watcher", "triage")
    
    # Triage → conditional routing
    graph.add_conditional_edges(
        "triage",
        route_after_triage,
        {
            "researcher": "researcher",
            "vision": "vision",
            "drafter": "drafter",
        }
    )
    
    # Research/Vision → Drafter
    graph.add_edge("researcher", "drafter")
    graph.add_edge("vision", "drafter")
    
    # Drafter → Action → END
    graph.add_edge("drafter", "action")
    graph.add_edge("action", END)
    
    return graph


def compile_graph():
    """Compile the graph for execution."""
    graph = build_graph()
    compiled = graph.compile()
    logger.info("✅ LangGraph pipeline compiled successfully")
    return compiled


# Create the compiled graph instance
pipeline = compile_graph()
