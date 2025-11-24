
import os
import sys
from typing import Dict, Any, List, Optional, TypedDict
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search.search import query_exa
from RAG.search_chunks import query_pinecone

# Initialize LLM (Single instance for nodes)
llm = None
try:
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
except:
    pass
if not llm:
    try:
        llm = ChatOpenAI(model="gpt-4o", temperature=0)
    except:
        pass

# --- State Definition ---
class ComplianceState(TypedDict):
    # The raw input text/query
    clause_text: str
    
    # Classification: 'definition', 'internal_ref', 'external_ref', 'direct_req'
    clause_type: str 
    
    # For Definition Path
    term_defined: Optional[str]
    is_new_definition: bool
    dependent_actionables: bool
    
    # For References
    resolved_text: str
    
    # Context & Result
    glossary_terms: Dict[str, str]
    org_context_data: Dict[str, Any] # HDFC/Navi details
    final_actionable: Optional[str] # The output task or None
    
    messages: List[Any] # History for debugging

# --- Nodes ---

def classifier_node(state: ComplianceState) -> Dict:
    print(f"\n[FLOW CHECK] Entering Node: Classifier")
    clause = state["clause_text"]
    print(f"[INPUT] Text: {clause[:100]}...")
    
    # ... existing prompt logic ...
    prompt = f"""Classify the following regulatory text into ONE of these categories:
    - 'definition': Defines a term (e.g., " 'Custodian' means...")
    - 'internal_ref': Refers to another part of this document (e.g., "As per regulation 3...")
    - 'external_ref': Refers to a different law/act (e.g., "As per SEBI Act 1992...")
    - 'direct_req': A standalone requirement (e.g., "The custodian shall submit...")

    Text: "{clause}"
    
    Return ONLY the category key (definition, internal_ref, external_ref, direct_req).
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    category = response.content.strip().lower()
    
    # Fallback normalization
    if "definition" in category: category = "definition"
    elif "internal" in category: category = "internal_ref"
    elif "external" in category: category = "external_ref"
    else: category = "direct_req"
    
    print(f"[OUTPUT] Classification: {category}")
    return {"clause_type": category}

def fetch_regulation_node(state: ComplianceState) -> Dict:
    print(f"\n[FLOW CHECK] Entering Node: Fetch Regulation (Orchestrator)")
    query = state["clause_text"]
    
    # ... existing entity extraction ...
    prompt_entity = f"Extract entity from '{query}'. Return ONLY entity name or 'GENERIC'."
    entity = llm.invoke([HumanMessage(content=prompt_entity)]).content.strip().replace("```", "")
    print(f"[LOGIC] Extracted Entity: {entity}")
    
    role_search_term = query
    if entity != "GENERIC":
        # ... existing role logic ...
        try:
            print(f"[TOOL CALL] Exa Search: '{entity} business model custodian mutual fund client SEBI role'")
            role_info = query_exa(f"{entity} business model custodian mutual fund client SEBI role")
            role_context = role_info.choices[0].message.content if hasattr(role_info, 'choices') else str(role_info)
            
            prompt_role = f"""Given this entity info: {role_context[:500]}...
            Map '{entity}' to one of these SEBI Custodian Regulation roles:
            - 'Custodian' (The provider)
            - 'Client' (The user, e.g., Mutual Fund, FPI)
            Return ONLY the role keyword.
            """
            role = llm.invoke([HumanMessage(content=prompt_role)]).content.strip()
            print(f"[LOGIC] Mapped Role: {role}")
            
            if "Client" in role or "Mutual Fund" in role:
                role_search_term = "agreement with client mutual fund obligations reconciliation of holdings"
            elif "Custodian" in role:
                role_search_term = "obligations of custodian code of conduct internal controls"
                
        except Exception as e:
            print(f"[ERROR] Role search failed: {e}")

    print(f"[TOOL CALL] RAG Query (Pinecone): '{role_search_term}'")
    matches = query_pinecone(role_search_term, top_k=3)
    
    if not matches:
        return {"resolved_text": "No specific regulations found."}
    
    combined_clauses = ""
    for i, m in enumerate(matches, 1):
        combined_clauses += f"CLAUSE {i}: {m['metadata']['text']}\n\n"
        
    print(f"[OUTPUT] Fetched {len(matches)} clauses.")
    return {"resolved_text": combined_clauses}

def definition_analysis_node(state: ComplianceState) -> Dict:
    print(f"\n[FLOW CHECK] Entering Node: Definition Analysis")
    clause = state["clause_text"]
    
    # ... extract term ...
    prompt_extract = f"Extract the term being defined in this text: '{clause}'. Return ONLY the term."
    term = llm.invoke([HumanMessage(content=prompt_extract)]).content.strip()
    print(f"[LOGIC] Extracted Term: {term}")
    
    print(f"[TOOL CALL] RAG Query (Pinecone): '{term}' (Checking usage)")
    matches = query_pinecone(term, top_k=3)
    
    is_new = len(matches) < 2
    
    has_dependency = False
    if not is_new:
        context = "\n".join([m['metadata']['text'] for m in matches])
        prompt_dep = f"""Term: {term}
        Other Clauses: {context}
        Do these other clauses contain actionable obligations that depend on this term? Return YES or NO.
        """
        dep_resp = llm.invoke([HumanMessage(content=prompt_dep)]).content.strip().upper()
        has_dependency = "YES" in dep_resp
        
    print(f"[OUTPUT] New Definition: {is_new}, Dependencies: {has_dependency}")
    return {
        "term_defined": term,
        "is_new_definition": is_new,
        "dependent_actionables": has_dependency
    }

def reference_resolver_node(state: ComplianceState) -> Dict:
    print(f"\n[FLOW CHECK] Entering Node: Reference Resolver")
    clause = state["clause_text"]
    
    print(f"[TOOL CALL] RAG Query (Pinecone): '{clause}' (Resolving reference)")
    matches = query_pinecone(clause, top_k=1)
    resolved = matches[0]['metadata']['text'] if matches else "Could not resolve reference."
    print(f"[OUTPUT] Resolved Text Length: {len(resolved)}")
    
    return {"resolved_text": resolved}

def glossary_node(state: ComplianceState) -> Dict:
    print(f"\n[FLOW CHECK] Entering Node: Glossary")
    text = state.get("resolved_text") or state["clause_text"]
    
    prompt = f"""You are a text normalizer for SEBI regulations.
    Goal: Normalize terms in the text below to standard legal terms.
    Replacements:
    - 'AMC' -> 'Asset Management Company'
    - 'MF' -> 'Mutual Fund'
    - 'FPI' -> 'Foreign Portfolio Investor'
    Input Text:
    {text}
    Output: Return the normalized text. Do NOT explain.
    """
    normalized = llm.invoke([HumanMessage(content=prompt)]).content.strip()
    
    if len(normalized) < len(text) * 0.6:
        print("[LOGIC] Safety Revert: Output too short, keeping original.")
        normalized = text
        
    print(f"[OUTPUT] Text Normalized.")
    return {"resolved_text": normalized}

def org_context_node(state: ComplianceState) -> Dict:
    print(f"\n[FLOW CHECK] Entering Node: Organization Context")
    text = state.get("resolved_text") or state["clause_text"]
    
    prompt_entity = f"""Extract the specific Organization or Entity name mentioned in this query (e.g., 'HDFC AMC', 'Navi Mutual Fund').
    Query: "{state['clause_text']}"
    Rules:
    1. Return ONLY the entity name as a plain string.
    2. If no specific entity is named, return 'GENERIC'.
    3. Do NOT generate any code, Python scripts, or explanations.
    4. Do NOT format as markdown.
    """
    entity = llm.invoke([HumanMessage(content=prompt_entity)]).content.strip().replace("```", "").replace("python", "").strip()
    print(f"[LOGIC] Extracted Entity for Context: {entity}")
    
    context_data = {}
    
    if entity != "GENERIC":
        print(f"[TOOL CALL] Exa Search: '{entity} AUM entity type registration status SEBI'")
        try:
            search_resp = query_exa(f"{entity} AUM entity type registration status SEBI")
            if hasattr(search_resp, 'choices'):
                context_text = search_resp.choices[0].message.content
            else:
                context_text = str(search_resp)
            
            print(f"[OUTPUT] Context Found: {context_text[:100]}...")
            context_data = {"entity": entity, "info": context_text}
        except Exception as e:
            print(f"[ERROR] Search Error: {e}")
            context_data = {"error": str(e)}
            
    return {"org_context_data": context_data}

def actionable_node(state: ComplianceState) -> Dict:
    print(f"\n[FLOW CHECK] Entering Node: Actionable Determination")
    text = state.get("resolved_text") or state["clause_text"]
    context = state.get("org_context_data", {})
    
    prompt = f"""You are a Compliance Officer. Determine the actionable requirements for the organization.
    
    1. ORGANIZATION CONTEXT:
    {context}
    
    2. REGULATORY CLAUSES (Retrieved from Database):
    {text}
    
    TASK:
    - For EACH clause above, determine if it creates an obligation for the Organization.
    - **CRITICAL:** If the Organization is a 'Client' (e.g. Mutual Fund) and the rule says "The Custodian shall enter into an agreement with the client", this IS an actionable requirement for the Organization (they must sign the agreement).
    - Interpret RECIPROCAL obligations. If a Custodian must do X with/for the Organization, the Organization often has a corresponding duty to facilitate X.
    
    OUTPUT FORMAT:
    - Clause [X]: [Actionable] - [Specific Obligation for the Organization]
    - Clause [Y]: [Not Applicable] - Reason
    """
    
    result = llm.invoke([HumanMessage(content=prompt)]).content.strip()
    print(f"[OUTPUT] Final Decision Generated.")
    return {"final_actionable": result}
