"""
FastAPI endpoint for SEBI Compliance Agent

Endpoints:
- POST /process_clause - Process a single clause
- POST /batch_process - Process all chunks for an organization  
- GET /compliance/{org_name} - Get saved compliance report
"""

import os
import json
from typing import Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.agent1 import process_clause
from agents.batch_processor import load_chunks, process_all_chunks, save_results


app = FastAPI(
    title="SEBI Compliance Agent API",
    description="Generate compliance requirements from SEBI Custodian Regulations",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ClauseRequest(BaseModel):
    clause_text: str
    org_name: str = "HDFC AMC"  # Default to HDFC AMC
    chunk_id: Optional[str] = None


class ClauseResponse(BaseModel):
    chunk_id: Optional[str]
    clause_type: str
    is_applicable: bool
    actionables: list
    actionable_count: int
    term_defined: Optional[str]
    referenced_regulations: list


class BatchRequest(BaseModel):
    org_name: str = "HDFC AMC"
    limit: int = 0  # 0 = all chunks


class BatchStatusResponse(BaseModel):
    status: str
    org_name: str
    message: str


# =============================================================================
# BATCH PROCESSING STATUS
# =============================================================================

batch_status = {}


def run_batch_processing(org_name: str, limit: int):
    """Background task for batch processing"""
    global batch_status
    batch_status[org_name] = {"status": "running", "started": datetime.now().isoformat()}
    
    try:
        chunks_path = os.path.join(os.path.dirname(__file__), "data/1758886606773_chunks.json")
        chunks = load_chunks(chunks_path)
        
        if limit > 0:
            chunks = chunks[:limit]
        
        output = process_all_chunks(chunks, org_name)
        save_results(output, org_name, os.path.join(os.path.dirname(__file__), "data"))
        
        batch_status[org_name] = {
            "status": "completed",
            "total_actionables": output["total_actionables"],
            "applicable_chunks": output["applicable_chunks"],
            "completed": datetime.now().isoformat()
        }
    except Exception as e:
        batch_status[org_name] = {
            "status": "error",
            "error": str(e),
            "completed": datetime.now().isoformat()
        }


# =============================================================================
# ENDPOINTS
# =============================================================================

@app.get("/")
def root():
    return {
        "name": "SEBI Compliance Agent API",
        "version": "1.0.0",
        "endpoints": {
            "POST /process_clause": "Process a single regulatory clause",
            "POST /batch_process": "Start batch processing for an organization",
            "GET /batch_status/{org_name}": "Check batch processing status",
            "GET /compliance/{org_name}": "Get latest compliance report"
        }
    }


@app.post("/process_clause", response_model=ClauseResponse)
def process_single_clause(request: ClauseRequest):
    """Process a single regulatory clause and return actionables"""
    try:
        result = process_clause(
            clause_text=request.clause_text,
            org_name=request.org_name,
            chunk_id=request.chunk_id or ""
        )
        return ClauseResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch_process", response_model=BatchStatusResponse)
def start_batch_process(request: BatchRequest, background_tasks: BackgroundTasks):
    """Start batch processing of all chunks for an organization"""
    
    if request.org_name not in ["HDFC AMC", "Navi AMC"]:
        raise HTTPException(
            status_code=400, 
            detail="org_name must be 'HDFC AMC' or 'Navi AMC'"
        )
    
    # Check if already running
    if request.org_name in batch_status:
        if batch_status[request.org_name].get("status") == "running":
            return BatchStatusResponse(
                status="already_running",
                org_name=request.org_name,
                message="Batch processing is already running for this organization"
            )
    
    # Start background task
    background_tasks.add_task(run_batch_processing, request.org_name, request.limit)
    
    return BatchStatusResponse(
        status="started",
        org_name=request.org_name,
        message=f"Batch processing started for {request.org_name}"
    )


@app.get("/batch_status/{org_name}")
def get_batch_status(org_name: str):
    """Get status of batch processing"""
    if org_name not in batch_status:
        return {"status": "not_started", "org_name": org_name}
    return batch_status[org_name]


@app.get("/compliance/{org_name}")
def get_compliance_report(org_name: str):
    """Get the latest compliance report for an organization"""
    
    # Find latest JSON file
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    safe_name = org_name.lower().replace(" ", "_")
    
    matching_files = []
    for f in os.listdir(data_dir):
        if f.startswith(f"compliance_{safe_name}") and f.endswith(".json"):
            matching_files.append(f)
    
    if not matching_files:
        raise HTTPException(
            status_code=404, 
            detail=f"No compliance report found for {org_name}"
        )
    
    # Get the latest file
    latest_file = sorted(matching_files)[-1]
    
    with open(os.path.join(data_dir, latest_file), 'r') as f:
        return json.load(f)


@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
