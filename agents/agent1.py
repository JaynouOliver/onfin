"""
Agent Flow Diagram (Strict Compliance Flowchart):

[Start] -> [Classifier]
              |
              +---> (Definition) ----> [Definition Analysis]
              |                            |
              |                            v
              |                     [Is New & No Dep?] --(Yes)--> [No Actionable]
              |                            |
              |                          (No)
              |                            |
              |                            v
              +---> (Ref) -----------> [Ref Resolver] 
              |                            |
              |                            v
              +---> (Direct Req) ----> [Fetch Reg] -> [Glossary]
                                           |
                                           v
                                    [Org Context]
                                           |
                                           v
                                      [Actionable]
"""

import os
import sys
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import SystemMessage, HumanMessage

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Nodes and State
from agents.graph_nodes import (
    ComplianceState,
    classifier_node,
    definition_analysis_node,
    reference_resolver_node,
    glossary_node,
    org_context_node,
    actionable_node,
    fetch_regulation_node # New import
)

# --- Conditional Edges ---

def route_after_classifier(state: ComplianceState):
    """Routes based on clause classification"""
    c_type = state["clause_type"]
    if c_type == "definition":
        return "definition_analysis"
    elif "ref" in c_type: # internal_ref or external_ref
        return "reference_resolver"
    else: # direct_req
        # Logic change: If it's a direct requirement query, we assume we need to FETCH the regulation text first
        # unless we are sure the input IS the regulation.
        # For a chatbot, it's safe to route to fetcher.
        return "fetch_regulation"

def route_after_definition(state: ComplianceState):
    """Routes based on definition analysis (New/No Dep?)"""
    is_new = state.get("is_new_definition", False)
    has_dep = state.get("dependent_actionables", False)
    
    # If New Definition AND No Dependencies -> No Actionable
    if is_new and not has_dep:
        return "no_actionable" # End
    else:
        # If existing or has dependencies, treat as actionable logic
        return "actionable"

# --- Graph Construction ---

builder = StateGraph(ComplianceState)

# Add Nodes
builder.add_node("classifier", classifier_node)
builder.add_node("definition_analysis", definition_analysis_node)
builder.add_node("reference_resolver", reference_resolver_node)
builder.add_node("fetch_regulation", fetch_regulation_node) # New Node
builder.add_node("glossary", glossary_node)
builder.add_node("org_context", org_context_node)
builder.add_node("actionable", actionable_node)

# Entry
builder.add_edge(START, "classifier")

# Branching from Classifier
builder.add_conditional_edges(
    "classifier",
    route_after_classifier,
    {
        "definition_analysis": "definition_analysis",
        "reference_resolver": "reference_resolver",
        "fetch_regulation": "fetch_regulation" # Changed target
    }
)

# Branching from Definition Analysis
builder.add_conditional_edges(
    "definition_analysis",
    route_after_definition,
    {
        "no_actionable": END,
        "actionable": "actionable" # Jump straight to actionable determination (skipping glossary/context for pure defs? Or should it merge?)
        # Per diagram: If No -> Is New? -> Yes -> No Actionable.
        # If No -> Is New? -> No -> Do other clauses use? -> No -> No Actionable
        # If ... -> Yes -> Actionable.
        # For simplicity in this demo, we route to 'actionable' node to generate the final output.
    }
)

# Flow for References: Resolver -> Glossary -> Context -> Actionable
builder.add_edge("reference_resolver", "glossary")

# Flow for Direct/Glossary: Fetcher -> Glossary -> Context -> Actionable
builder.add_edge("fetch_regulation", "glossary") # Connect new node
builder.add_edge("glossary", "org_context")
builder.add_edge("org_context", "actionable")

# Exit
builder.add_edge("actionable", END)

# Compile
memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# System Prompt (kept for API compatibility, though logic is now in nodes)
SYSTEM_PROMPT = """You are a SEBI Compliance Agent utilizing a strict decision flowchart.
Your goal is to process regulatory clauses and determine specific actionable requirements for the organization.
"""

def run_agent():
    print("SEBI Compliance Agent (Strict Flowchart Mode)")
    print("Type 'exit' to quit.")
    
    config = {"configurable": {"thread_id": "thread-demo"}}
    
    while True:
        user_input = input("\nUser (Enter Clause/Query): ")
        if user_input.lower() in ["exit", "quit"]:
            break
            
        # Initialize state
        initial_state = {
            "clause_text": user_input,
            "messages": [] # Required structure
        }
        
        try:
            # Stream events
            # We filter for the final output or specific node updates
            events = graph.stream(initial_state, config, stream_mode="values")
            
            for event in events:
                # FULL EVENT LOGGING
                print(f"\n--- [DEBUG: EVENT PAYLOAD] ---\n{event}\n------------------------------")

                # Print progress based on what keys are in the event
                if "clause_type" in event:
                    print(f"-> Classified as: {event['clause_type']}")
                if "term_defined" in event and event["term_defined"]:
                    print(f"-> Definition Analysis: Term='{event['term_defined']}', New={event['is_new_definition']}")
                if "resolved_text" in event:
                    # Truncate for display
                    preview = event['resolved_text'][:50].replace('\n', ' ')
                    print(f"-> Text Processed: {preview}...")
                if "org_context_data" in event and event["org_context_data"]:
                    data = event["org_context_data"]
                    if "entity" in data:
                        print(f"-> Organization Context: Found data for {data['entity']}")
                if "final_actionable" in event:
                    print(f"\n[Final Result]: {event['final_actionable']}")
                    
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    run_agent()
