"""
SEBI Compliance Agent - LangGraph Implementation

FLOW DIAGRAM (Exact match to Miro flowchart):
==============================================

                                 +----------+
                                 |  Clause  |
                                 +----+-----+
                                      |
                                      v
                              +-------+--------+
                              |   Classifier   |
                              +-------+--------+
                                      |
          +---------------+-----------+-----------+---------------+
          |               |                       |               |
          v               v                       v               v
    +-----------+   +-----------+           +-----------+   +-------------+
    | Definition|   | Internal  |           | External  |   | Compliance  |
    |           |   | Reference |           | Reference |   | Requirement |
    +-----------+   +-----------+           +-----------+   | w/ no ref   |
          |               |                       |         +-------------+
          v               |                       |               |
    +-----------+         |                       |               |
    |  Search   |         |                       |               |
    | reference |         |                       |               |
    | clauses   |         |                       |               |
    | by        |         |                       |               |
    | glossary  |         |                       |               |
    +-----------+         |                       |               |
          |               |                       |               |
          v               |                       |               |
    +-----------+         |                       |               |
   /  Is this   \\        |                       |               |
  /   a new      \\       |                       |               |
  \\  definition? /       |                       |               |
   \\            /        |                       |               |
    +-----+-----+         |                       |               |
     Yes  |  No           |                       |               |
      |   |               |                       |               |
      |   v               |                       |               |
      | +-----------+     |                       |               |
      |/ Do other   \\    |                       |               |
      |\\ clauses use /    |                       |               |
      | \\ same def? /     |                       |               |
      |  +----+----+      |                       |               |
      |   No  |  Yes      |                       |               |
      |   |   |           |                       |               |
      |   |   v           |                       |               |
      |   | +-----------+ |                       |               |
      |   |/ Do those   \\|                       |               |
      |   |\\ clauses    /|                       |               |
      |   | \\ have any  /|                       |               |
      |   |  \\ action- / |                       |               |
      |   |   \\ able? /  |                       |               |
      |   |    +--+--+    |                       |               |
      |   |   No  | Yes   |                       |               |
      |   |   |   |       |                       |               |
      v   v   v   |       v                       v               |
    +-------+     |  +---------+            +---------+           |
    |  No   |     |  | Go to   |            |  Read   |           |
    | Action|     |  | portion |            | Regul-  |           |
    | able  |     |  | & fetch |            | ation   |           |
    +-------+     |  | clause  |            | Library |           |
                  |  +---------+            +---------+           |
                  |       |                       |               |
                  |       +-------+-------+-------+               |
                  |               |                               |
                  |               v                               |
                  |        +------+------+                        |
                  +------->|    Read     |<-----------------------+
                           |  Glossary   |
                           +------+------+
                                  |
                                  v
                           +------+------+
                           |    Read     |
                           | Organization|
                           |   Context   |
                           +------+------+
                                  |
                                  v
                           +------+------+
                           | Actionable  |
                           +-------------+

GRAPH EDGES:
============
START → classifier

classifier →(conditional)→ definition_analysis   (if clause_type == "definition")
classifier →(conditional)→ internal_reference    (if clause_type == "internal_ref")
classifier →(conditional)→ external_reference    (if clause_type == "external_ref")
classifier →(conditional)→ glossary              (if clause_type == "direct_req")

definition_analysis →(conditional)→ no_actionable   (if new OR no users OR no actionables)
definition_analysis →(conditional)→ glossary        (if has dependent actionables)

internal_reference → glossary
external_reference → glossary

glossary → org_context
org_context → actionable

actionable → END
no_actionable → END
"""

import os
import sys
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.memory import MemorySaver

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.graph_nodes import (
    ComplianceState,
    classifier_node,
    definition_analysis_node,
    internal_reference_node,
    external_reference_node,
    glossary_node,
    org_context_node,
    actionable_node,
    no_actionable_node,
    route_after_classifier,
    route_after_definition,
)


# =============================================================================
# GRAPH CONSTRUCTION
# Builds the LangGraph matching the flowchart exactly
# =============================================================================

def build_compliance_graph():
    """
    Build the compliance processing graph.
    
    Graph structure matches the Miro flowchart:
    - 1 entry node (classifier)
    - 4 classification paths (definition, internal_ref, external_ref, direct_req)
    - 3 decision diamonds for definitions
    - Merge point at glossary
    - Linear flow: glossary → org_context → actionable
    - 2 terminal nodes (actionable, no_actionable)
    """
    
    builder = StateGraph(ComplianceState)
    
    # -------------------------------------------------------------------------
    # ADD ALL NODES
    # -------------------------------------------------------------------------
    
    # Entry node
    builder.add_node("classifier", classifier_node)
    
    # Definition path (includes 3 decision diamonds)
    builder.add_node("definition_analysis", definition_analysis_node)
    
    # Reference resolution nodes
    builder.add_node("internal_reference", internal_reference_node)  # Go to portion & fetch
    builder.add_node("external_reference", external_reference_node)  # Read Regulation Library
    
    # Common path nodes
    builder.add_node("glossary", glossary_node)          # Read Glossary
    builder.add_node("org_context", org_context_node)    # Read Organization Context
    
    # Terminal nodes
    builder.add_node("actionable", actionable_node)      # Actionable
    builder.add_node("no_actionable", no_actionable_node)  # No Actionable
    
    # -------------------------------------------------------------------------
    # ADD EDGES
    # -------------------------------------------------------------------------
    
    # START → Classifier
    builder.add_edge(START, "classifier")
    
    # Classifier → (conditional routing based on clause_type)
    # Matches: Clause → Classifier → [Definition|Internal Ref|External Ref|Direct Req]
    builder.add_conditional_edges(
        "classifier",
        route_after_classifier,
        {
            "definition_analysis": "definition_analysis",
            "internal_reference": "internal_reference",
            "external_reference": "external_reference",
            "glossary": "glossary",  # Direct req goes straight to glossary
        }
    )
    
    # Definition Analysis → (conditional routing based on 3 decision diamonds)
    # Matches: Definition → Search by glossary → Is new? → Do others use? → Have actionables?
    builder.add_conditional_edges(
        "definition_analysis",
        route_after_definition,
        {
            "no_actionable": "no_actionable",
            "glossary": "glossary",
        }
    )
    
    # Reference paths merge at Glossary
    # Matches: Internal Ref → Go to portion & fetch → Read Glossary
    # Matches: External Ref → Read Regulation Library → Read Glossary
    builder.add_edge("internal_reference", "glossary")
    builder.add_edge("external_reference", "glossary")
    
    # Common path: Glossary → Org Context → Actionable
    # Matches: Read Glossary → Read Organization Context → Actionable
    builder.add_edge("glossary", "org_context")
    builder.add_edge("org_context", "actionable")
    
    # Terminal nodes → END
    builder.add_edge("actionable", END)
    builder.add_edge("no_actionable", END)
    
    # -------------------------------------------------------------------------
    # COMPILE GRAPH
    # -------------------------------------------------------------------------
    
    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    
    return graph


# Build the graph
graph = build_compliance_graph()

# System prompt for API compatibility
SYSTEM_PROMPT = """You are a SEBI Compliance Agent that processes regulatory clauses 
and generates actionable compliance requirements for organizations like HDFC AMC and Navi AMC.

You follow a strict flowchart:
1. Classify the clause (Definition, Internal Ref, External Ref, or Direct Requirement)
2. Resolve any references
3. Apply glossary normalization
4. Load organization context
5. Generate actionable compliance items"""


# =============================================================================
# SINGLE CLAUSE PROCESSOR
# =============================================================================

def process_clause(clause_text: str, org_name: str, chunk_id: str = "") -> dict:
    """
    Process a single clause through the graph and return actionables.
    
    Args:
        clause_text: The regulatory clause text
        org_name: "HDFC AMC" or "Navi AMC"
        chunk_id: Optional chunk ID for tracking
    
    Returns:
        dict with:
        - chunk_id: The chunk identifier
        - clause_type: Classification result
        - is_applicable: Whether clause applies to org
        - actionables: List of compliance action items
        - actionable_count: Number of actionables
        - term_defined: (for definitions) The term being defined
        - referenced_regulations: (for refs) List of referenced regulations
    """
    config = {"configurable": {"thread_id": f"clause-{chunk_id or 'single'}"}}
    
    initial_state = {
        "clause_text": clause_text,
        "chunk_id": chunk_id,
        "org_name": org_name,
        "messages": [],
    }
    
    # Run the graph
    final_state = None
    for event in graph.stream(initial_state, config, stream_mode="values"):
        final_state = event
    
    return {
        "chunk_id": chunk_id,
        "clause_type": final_state.get("clause_type", "unknown"),
        "is_applicable": final_state.get("is_applicable", False),
        "actionables": final_state.get("actionables", []),
        "actionable_count": final_state.get("actionable_count", 0),
        "term_defined": final_state.get("term_defined"),
        "referenced_regulations": final_state.get("referenced_regulations", []),
    }


# =============================================================================
# INTERACTIVE CLI
# =============================================================================

def run_agent():
    """Interactive CLI for testing the agent"""
    print("=" * 60)
    print("SEBI Compliance Agent")
    print("=" * 60)
    print("\nCommands:")
    print("  exit/quit - Exit")
    print("  org:HDFC  - Set organization to HDFC AMC")
    print("  org:Navi  - Set organization to Navi AMC")
    print("\n")
    
    org_name = "HDFC AMC"
    
    while True:
        user_input = input(f"\n[{org_name}] Enter clause: ").strip()
        
        if not user_input:
            continue
        
        if user_input.lower() in ["exit", "quit"]:
            break
        
        if user_input.lower().startswith("org:"):
            org = user_input[4:].strip()
            if "hdfc" in org.lower():
                org_name = "HDFC AMC"
            elif "navi" in org.lower():
                org_name = "Navi AMC"
            else:
                org_name = org
            print(f"Organization set to: {org_name}")
            continue
        
        try:
            result = process_clause(user_input, org_name)
            
            print(f"\n{'='*60}")
            print(f"RESULT")
            print(f"{'='*60}")
            print(f"Clause Type: {result['clause_type']}")
            print(f"Applicable: {result['is_applicable']}")
            print(f"Actionable Count: {result['actionable_count']}")
            
            if result['term_defined']:
                print(f"Term Defined: {result['term_defined']}")
            
            if result['referenced_regulations']:
                print(f"References: {result['referenced_regulations']}")
            
            if result['actionables']:
                print(f"\nActionables:")
                for i, action in enumerate(result['actionables'], 1):
                    print(f"  {i}. {action}")
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    run_agent()
