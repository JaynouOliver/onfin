
import os
import sys
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.messages import HumanMessage, SystemMessage

# Add project root to path to allow imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the agent graph and config from agent1.py
# We need to modify agent1.py slightly to expose the graph object cleanly or import it here.
# For now, let's assume we can import 'graph' and 'SYSTEM_PROMPT' from agent1
try:
    from agents.agent1 import graph, SYSTEM_PROMPT
except ImportError:
    # Fallback if running from root
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents"))
    from agents.agent1 import graph, SYSTEM_PROMPT

app = FastAPI(title="SEBI Compliance Agent API")

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default_thread"

class ChatResponse(BaseModel):
    response: str
    tool_calls: Optional[List[Dict[str, Any]]] = []

@app.get("/")
def health_check():
    return {"status": "ok", "service": "SEBI Compliance Agent"}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # Check if history exists, if not seed with System Prompt
        current_state = await graph.aget_state(config)
        input_messages = [HumanMessage(content=request.message)]
        
        if not current_state.values:
            input_messages.insert(0, SystemMessage(content=SYSTEM_PROMPT))
            
        # Stream events
        # Using astream for async compatibility
        # Ensure clause_text is passed as it's required by the graph state
        input_state = {
            "messages": input_messages,
            "clause_text": request.message
        }
        events = graph.astream(input_state, config, stream_mode="values")
        
        final_response = ""
        tool_actions = []
        
        async for event in events:
            # Capture final actionable result from the graph state
            if "final_actionable" in event and event["final_actionable"]:
                final_response = event["final_actionable"]

            if "messages" in event:
                last_msg = event["messages"][-1]
                
                # Capture tool calls for frontend visibility
                if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                    for tool_call in last_msg.tool_calls:
                        tool_actions.append({
                            "tool": tool_call['name'],
                            "args": tool_call['args']
                        })
                
                # Capture final AI response
                if last_msg.type == "ai" and not last_msg.tool_calls:
                    final_response = last_msg.content

        return ChatResponse(
            response=final_response,
            tool_calls=tool_actions
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

