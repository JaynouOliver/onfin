"""
Graph Nodes for SEBI Compliance Agent
Implements the flowchart logic for processing regulatory clauses

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

NODE MAPPING:
=============
1. Classifier           → classifier_node()
2. Definition Analysis  → definition_analysis_node() 
   (includes: search by glossary, check if new, check if used, check if actionable)
3. Internal Reference   → internal_reference_node()
   (Go to that portion and fetch clause)
4. External Reference   → external_reference_node()
   (Read Regulation Library)
5. Glossary             → glossary_node()
   (Read Glossary)
6. Org Context          → org_context_node()
   (Read Organization Context)
7. Actionable           → actionable_node()
8. No Actionable        → no_actionable_node()
"""

import os
import sys
import re
from typing import Dict, Any, List, Optional, TypedDict

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.config import (
    SEBI_GLOSSARY, 
    ABBREVIATION_EXPANSIONS,
    ORG_CONTEXTS,
    HDFC_AMC_CONTEXT,
    NAVI_AMC_CONTEXT,
    INTERNAL_REF_PATTERNS,
    EXTERNAL_REF_PATTERNS,
)
from search.search import query_exa
from RAG.search_chunks import query_pinecone, query_pinecone_by_id

# =============================================================================
# LLM INITIALIZATION
# =============================================================================

llm = None
try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0)
except:
    pass
if not llm:
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
    except:
        pass


# =============================================================================
# STATE DEFINITION
# =============================================================================

class ComplianceState(TypedDict):
    """
    State that flows through the graph.
    Each node reads/writes specific fields.
    """
    # Input
    clause_text: str
    chunk_id: str
    org_name: str  # "HDFC AMC" or "Navi AMC"
    
    # Classification (set by: classifier_node)
    clause_type: str  # definition, internal_ref, external_ref, direct_req
    
    # Definition Path (set by: definition_analysis_node)
    term_defined: Optional[str]
    is_new_definition: bool
    other_clauses_use_definition: bool
    dependent_clauses_have_actionables: bool
    
    # Reference Resolution (set by: internal_reference_node, external_reference_node)
    resolved_text: str
    referenced_regulations: List[str]
    
    # Glossary Output (set by: glossary_node)
    normalized_text: str
    glossary_terms_used: Dict[str, str]
    
    # Organization Context (set by: org_context_node)
    org_context: Dict[str, Any]
    
    # Final Output (set by: actionable_node, no_actionable_node)
    actionables: List[str]
    actionable_count: int
    is_applicable: bool
    
    # Metadata
    messages: List[Any]


# =============================================================================
# NODE 1: CLASSIFIER
# Matches flowchart: First circle after "Clause" input
# Routes to: Definition | Internal Reference | External Reference | Direct Req
# =============================================================================

def classifier_node(state: ComplianceState) -> Dict:
    """
    Classify clause into one of 4 types:
    - definition: Defines a term
    - internal_ref: References another regulation in same document
    - external_ref: References external law/act
    - direct_req: Standalone compliance requirement (no reference)
    """
    print(f"\n[NODE] Classifier")
    clause = state["clause_text"]
    print(f"[INPUT] Clause: {clause[:150]}...")
    
    # Quick pattern matching first
    clause_lower = clause.lower()
    
    # Check for definition patterns
    if any(pattern in clause_lower for pattern in ['"means"', "'means'", "shall mean", "means and includes"]):
        print(f"[OUTPUT] Classification: definition (pattern match)")
        return {"clause_type": "definition"}
    
    # Check for internal reference patterns
    for pattern in INTERNAL_REF_PATTERNS:
        if re.search(pattern, clause, re.IGNORECASE):
            print(f"[OUTPUT] Classification: internal_ref (pattern: {pattern})")
            return {"clause_type": "internal_ref"}
    
    # Check for external reference patterns
    for pattern in EXTERNAL_REF_PATTERNS:
        if re.search(pattern, clause, re.IGNORECASE):
            print(f"[OUTPUT] Classification: external_ref (pattern: {pattern})")
            return {"clause_type": "external_ref"}
    
    # Use LLM for ambiguous cases
    prompt = f"""Classify this regulatory text into ONE category:

1. 'definition' - Defines a term (contains "means", "shall mean", defines what something is)
2. 'internal_ref' - References another regulation in same document (mentions "regulation X", "sub-regulation", "clause (a)")
3. 'external_ref' - References external law (mentions other Acts, other SEBI regulations, RBI)
4. 'direct_req' - Standalone requirement (contains "shall", "must", "required to" without referencing other regulations)

Text: "{clause[:500]}"

Return ONLY one word: definition, internal_ref, external_ref, or direct_req"""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    category = response.content.strip().lower().replace("'", "").replace('"', '')
    
    # Normalize
    if "definition" in category:
        category = "definition"
    elif "internal" in category:
        category = "internal_ref"
    elif "external" in category:
        category = "external_ref"
    else:
        category = "direct_req"
    
    print(f"[OUTPUT] Classification: {category}")
    return {"clause_type": category}


# =============================================================================
# NODE 2A: DEFINITION ANALYSIS
# Matches flowchart: "Definition" → "Search reference clauses by glossary"
#                    → "Is this a new definition?" decision diamond
#                    → "Do other clauses use same definition?" decision diamond  
#                    → "Do those other clauses have any actionable?" decision diamond
# =============================================================================

def definition_analysis_node(state: ComplianceState) -> Dict:
    """
    For definitions, implements the 3-step decision flow:
    
    Step 1: Search reference clauses by glossary (extract term, search for it)
    Step 2: Is this a new definition? 
            - If yes → route to No Actionable
    Step 3: Do other clauses use same definition?
            - If no → route to No Actionable
    Step 4: Do those other clauses have any actionable that depends on definition?
            - If no → route to No Actionable
            - If yes → continue to Glossary
    """
    print(f"\n[NODE] Definition Analysis")
    print(f"[STEP] Search reference clauses by glossary")
    clause = state["clause_text"]
    
    # Step 1: Extract the term being defined (Search reference clauses by glossary)
    prompt = f"""Extract the term being defined in this text.
    
Text: "{clause[:500]}"

Return ONLY the term being defined (e.g., "custodian", "client", "securities").
If multiple terms, return the main one."""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    term = response.content.strip().strip('"\'')
    print(f"[STEP] Term defined: '{term}'")
    
    # Search for other clauses that use this term (via RAG/Pinecone)
    print(f"[STEP] Searching for clauses that use '{term}'")
    matches = query_pinecone(term, top_k=5)
    
    # Filter out the definition clause itself
    other_clauses = [m for m in matches if m['id'] != state.get('chunk_id', '')]
    
    # Step 2: Is this a new definition?
    # A definition is "new" if no other clauses reference it
    if len(other_clauses) == 0:
        print(f"[DECISION] Is this a new definition? YES (no other clauses use it)")
        print(f"[ROUTE] → No Actionable")
        return {
            "term_defined": term,
            "is_new_definition": True,
            "other_clauses_use_definition": False,
            "dependent_clauses_have_actionables": False,
        }
    
    print(f"[DECISION] Is this a new definition? NO (found {len(other_clauses)} clauses using it)")
    
    # Step 3: Do other clauses use same definition?
    # Already answered yes above if we reach here
    print(f"[DECISION] Do other clauses use same definition? YES")
    
    # Step 4: Do those other clauses have any actionable that depends on the definition?
    actionable_indicators = ["shall", "must", "required", "obligat", "comply", "ensure"]
    has_actionables = False
    
    for match in other_clauses:
        match_text = match['metadata'].get('text', '').lower()
        if any(indicator in match_text for indicator in actionable_indicators):
            has_actionables = True
            print(f"[FOUND] Actionable clause using this term: {match['id']}")
            break
    
    if has_actionables:
        print(f"[DECISION] Do those clauses have actionables? YES")
        print(f"[ROUTE] → Glossary → Org Context → Actionable")
    else:
        print(f"[DECISION] Do those clauses have actionables? NO")
        print(f"[ROUTE] → No Actionable")
    
    return {
        "term_defined": term,
        "is_new_definition": False,
        "other_clauses_use_definition": True,
        "dependent_clauses_have_actionables": has_actionables,
    }


# =============================================================================
# NODE 2B: INTERNAL REFERENCE RESOLVER
# Matches flowchart: "Internal Reference" → 
#                    "Go to that portion of this circular directly and fetch clause"
# =============================================================================

def internal_reference_node(state: ComplianceState) -> Dict:
    """
    For internal references:
    Go to that portion of this circular (same PDF) and fetch the referenced clause.
    Uses RAG to retrieve the referenced regulation from Pinecone.
    """
    print(f"\n[NODE] Internal Reference Resolver")
    print(f"[STEP] Go to that portion of this circular directly and fetch clause")
    clause = state["clause_text"]
    
    # Extract regulation references from the clause
    referenced_regs = []
    for pattern in INTERNAL_REF_PATTERNS:
        matches = re.findall(pattern, clause, re.IGNORECASE)
        referenced_regs.extend(matches)
    
    print(f"[FOUND] References to: {referenced_regs}")
    
    if not referenced_regs:
        # No specific reference found, use semantic search
        print(f"[SEARCH] No explicit reference, using semantic search")
        matches = query_pinecone(clause, top_k=2)
        resolved_text = clause
        if matches:
            resolved_text += "\n\n[RELATED REGULATIONS]\n"
            for m in matches:
                resolved_text += f"\n{m['metadata'].get('text', '')[:500]}"
    else:
        # Fetch specific regulations from the same document
        resolved_text = clause + "\n\n[REFERENCED REGULATIONS FROM SAME CIRCULAR]\n"
        for ref in referenced_regs[:3]:  # Limit to 3 references
            search_query = f"regulation {ref}"
            print(f"[FETCH] Fetching regulation {ref}")
            matches = query_pinecone(search_query, top_k=1)
            if matches:
                resolved_text += f"\nRegulation {ref}:\n{matches[0]['metadata'].get('text', '')[:500]}"
    
    print(f"[OUTPUT] Resolved text length: {len(resolved_text)}")
    return {
        "resolved_text": resolved_text,
        "referenced_regulations": referenced_regs,
    }


# =============================================================================
# NODE 2C: EXTERNAL REFERENCE RESOLVER
# Matches flowchart: "External Reference" → "Read Regulation Library of Reference"
# =============================================================================

def external_reference_node(state: ComplianceState) -> Dict:
    """
    For external references:
    Read Regulation Library of Reference (external acts, other SEBI regulations).
    Uses web search (Exa) to get context about external regulations.
    """
    print(f"\n[NODE] External Reference Resolver")
    print(f"[STEP] Read Regulation Library of Reference")
    clause = state["clause_text"]
    
    # Identify which external regulation is referenced
    external_refs = []
    for pattern in EXTERNAL_REF_PATTERNS:
        if re.search(pattern, clause, re.IGNORECASE):
            external_refs.append(pattern)
    
    print(f"[FOUND] External references: {external_refs}")
    
    # Build resolved text with external law context
    resolved_text = clause + "\n\n[EXTERNAL REGULATION LIBRARY]\n"
    
    # Add known external regulation context
    if "Companies Act" in clause:
        resolved_text += "- Companies Act, 2013: Defines corporate governance, change in control\n"
    if "SEBI Act" in clause or "Securities and Exchange Board of India Act" in clause:
        resolved_text += "- SEBI Act, 1992: Primary securities regulation act\n"
    if "Securities Contracts" in clause:
        resolved_text += "- Securities Contracts (Regulation) Act, 1956: Defines securities\n"
    if "Banking" in clause:
        resolved_text += "- Banking Regulation Act, 1949: Banking company definitions\n"
    if "RBI" in clause or "Reserve Bank" in clause:
        resolved_text += "- RBI Guidelines: Banking and forex regulations\n"
    
    # Use web search for additional context
    try:
        if external_refs:
            search_query = f"{external_refs[0]} SEBI compliance requirements"
            print(f"[SEARCH] Exa search: {search_query}")
            result = query_exa(search_query)
            if hasattr(result, 'choices') and result.choices:
                context = result.choices[0].message.content[:500]
                resolved_text += f"\n[Additional Context from Web]\n{context}"
    except Exception as e:
        print(f"[ERROR] External search failed: {e}")
    
    return {
        "resolved_text": resolved_text,
        "referenced_regulations": external_refs,
    }


# =============================================================================
# NODE 3: GLOSSARY
# Matches flowchart: "Read Glossary" circle
# All non-definition paths merge here before Org Context
# =============================================================================

def glossary_node(state: ComplianceState) -> Dict:
    """
    Read Glossary: Normalize terms using the SEBI glossary.
    Expands abbreviations and adds definitions for key terms.
    """
    print(f"\n[NODE] Read Glossary")
    text = state.get("resolved_text") or state["clause_text"]
    
    # Track which terms were normalized
    terms_used = {}
    normalized = text
    
    # Apply abbreviation expansions
    for abbrev, expansion in ABBREVIATION_EXPANSIONS.items():
        if abbrev in normalized and expansion not in normalized:
            normalized = normalized.replace(abbrev, f"{abbrev} ({expansion})")
            terms_used[abbrev] = expansion
    
    # Apply glossary definitions for key terms
    key_terms = ["custodian", "client", "custodial services", "custody account", "securities", "goods"]
    for term in key_terms:
        if term.lower() in normalized.lower() and term in SEBI_GLOSSARY:
            terms_used[term] = SEBI_GLOSSARY[term]
    
    print(f"[OUTPUT] Terms normalized: {list(terms_used.keys())}")
    return {
        "normalized_text": normalized,
        "glossary_terms_used": terms_used,
    }


# =============================================================================
# NODE 4: ORGANIZATION CONTEXT
# Matches flowchart: "Read Organization Context" circle
# =============================================================================

def org_context_node(state: ComplianceState) -> Dict:
    """
    Read Organization Context: Load context for HDFC AMC or Navi AMC.
    Includes: number of schemes, custodians, Gold/Silver ETFs, AUM, listed status.
    """
    print(f"\n[NODE] Read Organization Context")
    org_name = state.get("org_name", "")
    
    # Try to get preloaded context
    context = None
    for key, ctx in ORG_CONTEXTS.items():
        if key.lower() in org_name.lower():
            context = ctx
            print(f"[FOUND] Preloaded context for: {key}")
            break
    
    # Fallback to web search if not found
    if context is None:
        print(f"[SEARCH] No preloaded context, searching for: {org_name}")
        try:
            result = query_exa(f"{org_name} mutual fund AMC SEBI registration schemes")
            if hasattr(result, 'choices') and result.choices:
                search_context = result.choices[0].message.content
                context = {
                    "entity_name": org_name,
                    "role_in_custodian_regulations": "Client",
                    "search_result": search_context[:1000],
                    "compliance_factors": {"unknown": True}
                }
        except Exception as e:
            print(f"[ERROR] Org search failed: {e}")
            context = {
                "entity_name": org_name,
                "role_in_custodian_regulations": "Client",
                "compliance_factors": {}
            }
    
    return {"org_context": context}


# =============================================================================
# NODE 5: ACTIONABLE GENERATOR
# Matches flowchart: "Actionable" terminal circle
# =============================================================================

def actionable_node(state: ComplianceState) -> Dict:
    """
    Actionable: Generate actionable compliance items.
    Categories: VERIFY, DOCUMENT, MONITOR, REPORT
    """
    print(f"\n[NODE] Actionable Generator")
    
    text = state.get("normalized_text") or state.get("resolved_text") or state["clause_text"]
    org_context = state.get("org_context", {})
    org_name = org_context.get("entity_name", state.get("org_name", "Organization"))
    
    # Check applicability based on organization role
    org_role = org_context.get("role_in_custodian_regulations", "Client")
    
    prompt = f"""You are a Compliance Officer at {org_name} generating actionable compliance items.

CONTEXT:
- {org_name} is a MUTUAL FUND AMC (Asset Management Company)
- {org_name} is a CLIENT of custodians (they hire custodians to hold their assets)
- {org_name} is NOT a custodian themselves
- Has Gold ETF: {org_context.get('has_gold_etf', False)}
- Has Silver ETF: {org_context.get('has_silver_etf', False)}
- Number of Custodians: {org_context.get('custodian_count', 1)}

REGULATORY CLAUSE FROM SEBI CUSTODIAN REGULATIONS:
{text[:1500]}

GENERATE COMPLIANCE ACTIONABLES using these categories:

1. VERIFY: What must {org_name} verify their custodian is doing?
   - Even custodian obligations create VERIFICATION duties for clients
   - Example: "Custodian shall maintain records" → Client must "Verify custodian maintains records"

2. DOCUMENT: What documentation must {org_name} maintain?
   - Agreements, confirmations, audit trails

3. MONITOR: What ongoing monitoring is required?
   - Periodic checks, reviews, audits

4. REPORT: What must be reported and to whom?
   - Board reports, SEBI filings, investor disclosures

RULES:
- Generate 3-8 actionables per clause
- ONLY mark as NOT_APPLICABLE if clause specifically mentions gold/silver custody AND org has no Gold/Silver ETF
- Registration requirements for custodians still create DUE DILIGENCE actionables for clients
- Be specific but not repetitive

OUTPUT FORMAT:
NOT_APPLICABLE: [reason] (ONLY if truly not applicable)

OR

ACTIONABLE: [VERIFY] specific action
ACTIONABLE: [DOCUMENT] specific action  
ACTIONABLE: [MONITOR] specific action
ACTIONABLE: [REPORT] specific action"""

    response = llm.invoke([HumanMessage(content=prompt)])
    result = response.content.strip()
    
    # Parse actionables
    actionables = []
    is_applicable = True
    
    if result.startswith("NOT_APPLICABLE"):
        is_applicable = False
        actionables = []
        print(f"[OUTPUT] Not applicable: {result}")
    else:
        for line in result.split('\n'):
            if line.strip().startswith("ACTIONABLE:"):
                action = line.replace("ACTIONABLE:", "").strip()
                if action:
                    actionables.append(action)
    
    print(f"[OUTPUT] Generated {len(actionables)} actionables, Applicable: {is_applicable}")
    
    return {
        "actionables": actionables,
        "actionable_count": len(actionables),
        "is_applicable": is_applicable,
    }


# =============================================================================
# NODE 6: NO ACTIONABLE (Terminal)
# Matches flowchart: "No Actionable" terminal circle
# =============================================================================

def no_actionable_node(state: ComplianceState) -> Dict:
    """
    No Actionable: Terminal node for definitions without dependencies.
    Reached when:
    - Definition is new (no other clauses use it)
    - Other clauses use it but none have actionables
    """
    print(f"\n[NODE] No Actionable")
    print(f"[REASON] Definition clause with no dependent actionables")
    return {
        "actionables": [],
        "actionable_count": 0,
        "is_applicable": False,
    }


# =============================================================================
# ROUTING FUNCTIONS
# These implement the decision diamonds in the flowchart
# =============================================================================

def route_after_classifier(state: ComplianceState) -> str:
    """
    Route based on clause classification.
    
    Classifier output → Next node:
    - definition   → definition_analysis
    - internal_ref → internal_reference
    - external_ref → external_reference
    - direct_req   → glossary (skips reference resolution)
    """
    clause_type = state.get("clause_type", "direct_req")
    
    routes = {
        "definition": "definition_analysis",
        "internal_ref": "internal_reference",
        "external_ref": "external_reference",
        "direct_req": "glossary",  # "Compliance Requirement /w no reference"
    }
    
    return routes.get(clause_type, "glossary")


def route_after_definition(state: ComplianceState) -> str:
    """
    Route based on definition analysis (implements 3 decision diamonds):
    
    1. Is this a new definition?
       - YES → No Actionable
       - NO  → continue
    
    2. Do other clauses use same definition?
       - NO  → No Actionable
       - YES → continue
    
    3. Do those other clauses have any actionable that depends on the definition?
       - NO  → No Actionable
       - YES → Glossary → Org Context → Actionable
    """
    is_new = state.get("is_new_definition", False)
    other_use = state.get("other_clauses_use_definition", False)
    has_deps = state.get("dependent_clauses_have_actionables", False)
    
    # Decision 1: New definition that nothing uses → No actionable
    if is_new:
        return "no_actionable"
    
    # Decision 2: Other clauses don't use it → No actionable
    if not other_use:
        return "no_actionable"
    
    # Decision 3: Other clauses use it but none have actionables → No actionable
    if not has_deps:
        return "no_actionable"
    
    # All decisions passed: Continue to Glossary
    return "glossary"
