# SEBI Compliance Agent - Flow Design

## Architecture Overview

```
                              +-------------------+
                              |      Clause       |
                              |    (Input Text)   |
                              +--------+----------+
                                       |
                                       v
                              +--------+----------+
                              |    CLASSIFIER     |
                              | (Pattern + LLM)   |
                              +--------+----------+
                                       |
           +---------------------------+---------------------------+
           |                           |                           |
           v                           v                           v
   +-------+-------+           +-------+-------+           +-------+-------+
   |  Definition   |           | Internal Ref  |           | External Ref  |
   +-------+-------+           +-------+-------+           +-------+-------+
           |                           |                           |
           v                           |                           |
   +-------+-------+                   |                           |
   |  DEFINITION   |                   |                           |
   |   ANALYSIS    |                   |                           |
   +-------+-------+                   |                           |
           |                           |                           |
     +-----+-----+                     |                           |
     |           |                     v                           v
    New?     Has Deps?        +-------+-------+           +-------+-------+
     |           |            |   INTERNAL    |           |   EXTERNAL    |
     v           v            |   REFERENCE   |           |   REFERENCE   |
+----+----+ +----+----+       |   RESOLVER    |           |   RESOLVER    |
|   NO    | |  YES    |       | (Query RAG)   |           | (Web Search)  |
|ACTIONABLE|    |     |       +-------+-------+           +-------+-------+
+---------+    |     |                |                           |
               |     +----------------+---------------------------+
               |                      |
               |            +---------v---------+
               |            |   Direct Req      |
               |            +---------+---------+
               |                      |
               +----------------------+
                                      |
                                      v
                              +-------+-------+
                              |   GLOSSARY    |
                              | (Normalize    |
                              |  Terms)       |
                              +-------+-------+
                                      |
                                      v
                              +-------+-------+
                              | ORG CONTEXT   |
                              | (HDFC/Navi    |
                              |  Data)        |
                              +-------+-------+
                                      |
                                      v
                              +-------+-------+
                              |  ACTIONABLE   |
                              |  GENERATOR    |
                              | (VERIFY/DOC/  |
                              |  MONITOR/RPT) |
                              +-------+-------+
                                      |
                                      v
                              +-------+-------+
                              |    OUTPUT     |
                              | Compliance    |
                              | Requirements  |
                              +---------------+
```

## Node Descriptions

### 1. CLASSIFIER
- **Input**: Raw clause text
- **Logic**: 
  - Pattern matching for definitions ("means", "shall mean")
  - Pattern matching for internal refs ("regulation X", "sub-regulation")
  - Pattern matching for external refs ("SEBI Act", "Companies Act")
  - LLM fallback for ambiguous cases
- **Output**: Classification type (definition/internal_ref/external_ref/direct_req)

### 2. DEFINITION ANALYSIS
- **Input**: Definition clause
- **Logic**:
  - Extract term being defined
  - Query RAG to find clauses using this term
  - Check if dependent clauses have actionables
- **Output**: Decision to continue or mark as NO_ACTIONABLE

### 3. INTERNAL REFERENCE RESOLVER
- **Input**: Clause with internal references
- **Logic**:
  - Extract regulation numbers from text
  - Query Pinecone for referenced regulations
  - Append referenced text to context
- **Output**: Resolved text with referenced regulations

### 4. EXTERNAL REFERENCE RESOLVER
- **Input**: Clause with external references
- **Logic**:
  - Identify external act/regulation
  - Add context about referenced law
  - Optionally use web search for details
- **Output**: Resolved text with external context

### 5. GLOSSARY
- **Input**: Resolved clause text
- **Logic**:
  - Apply SEBI glossary definitions
  - Expand abbreviations (AMC, SEBI, etc.)
  - Track terms used
- **Output**: Normalized text with glossary context

### 6. ORG CONTEXT
- **Input**: Normalized text
- **Logic**:
  - Load preloaded org context (HDFC/Navi)
  - Add scheme information, custodian details
  - Flag special conditions (Gold ETF, Listed, etc.)
- **Output**: Text + Organization context

### 7. ACTIONABLE GENERATOR
- **Input**: Text + Org Context
- **Logic**:
  - Generate actionables in 4 categories:
    - VERIFY: What to verify custodian does
    - DOCUMENT: What documentation to maintain
    - MONITOR: What ongoing monitoring required
    - REPORT: What to report and to whom
  - Filter based on org applicability
- **Output**: List of specific compliance actionables

## Data Flow

```
PDF Document
     |
     v
[Text Extraction] --> data/1758886606773.txt
     |
     v
[Chunking] --> data/1758886606773_chunks.json (68 chunks)
     |
     v
[Upload to Pinecone] --> Vector Store (RAG)
     |
     v
[Batch Processor] --> Process each chunk through agent graph
     |
     v
[Compliance Report] --> JSON + TXT files per organization
```

## Expected Output

| Organization | Provisions | Multiplier | Expected Actionables |
|--------------|------------|------------|---------------------|
| HDFC AMC     | 178        | ~3.8x      | ~680               |
| Navi AMC     | 178        | ~2.2x      | ~400               |

### Why Different Multipliers?

**HDFC AMC (Higher)**:
- 100+ schemes vs Navi's 30
- Has Gold ETF and Silver ETF
- Multiple custodians (2)
- Listed entity
- Higher AUM = more scrutiny

**Navi AMC (Lower)**:
- Fewer schemes (~30)
- No Gold/Silver ETFs
- Single custodian
- Not listed
- Smaller AUM

## Files Structure

```
onfinance/
├── agents/
│   ├── agent1.py          # LangGraph definition
│   ├── graph_nodes.py     # Node implementations
│   ├── config.py          # Glossary + Org Context
│   └── batch_processor.py # Batch processing script
├── RAG/
│   ├── upload_to_pinecone.py
│   └── search_chunks.py
├── search/
│   └── search.py          # Exa web search
├── data/
│   ├── 1758886606773.pdf
│   ├── 1758886606773_chunks.json
│   └── compliance_*.json  # Output files
├── api.py                 # FastAPI endpoints
└── requirements.txt
```

## API Endpoints

- `POST /process_clause` - Process single clause
- `POST /batch_process` - Start batch processing
- `GET /batch_status/{org}` - Check processing status
- `GET /compliance/{org}` - Get compliance report

