from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
import shutil
import json
from pathlib import Path
from agent1_parse_mandate import create_parse_agent
from agent2_filter_companies import create_filter_agent
from urllib.parse import unquote

router = APIRouter(prefix="/api", tags=["fund-sourcing"])

# Pre-create agents (runs logging once)
parse_agent = create_parse_agent()
filter_agent = create_filter_agent()

from langchain_classic.callbacks.base import BaseCallbackHandler
from langchain_classic.schema import AgentAction, AgentFinish

class UITracer(BaseCallbackHandler):
    def __init__(self):
        self.trace = []
    
    def on_agent_action(self, action: AgentAction, **kwargs) -> None:
        self.trace.append(f"🧠 Thought: {action.log}\n🚀 Action: {action.tool}")
    
    def on_tool_start(self, serialized: dict, tool, **kwargs) -> None:
        self.trace.append(f"🔧 Tool starting: {serialized.get('name', tool)}")
    
    def on_tool_end(self, output, **kwargs) -> None:
        self.trace.append(f"📄 Tool result: {output}")
    
    def on_agent_finish(self, finish: AgentFinish, **kwargs) -> None:
        self.trace.append(f"✅ Final Answer: {finish.log}")


@router.post("/parse-mandate")
async def parse_mandate(
        pdf: UploadFile = File(..., description="Fund mandate PDF"),
        query: str = Form("", description="Optional query")
):
    """Agent 1: PDF + query → Extract criteria JSON"""
    if not pdf.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    # Save uploaded PDF to folder
    folder = Path("../input_fund_mandate")
    folder.mkdir(exist_ok=True)
    pdf_path = folder / pdf.filename
    with open(pdf_path, "wb") as buffer:
        shutil.copyfileobj(pdf.file, buffer)

    input_prompt = f"Scan input_fund_mandate/ and extract criteria. Query: {query}"

    try:
        tracer = UITracer()
        config = {"callbacks": [tracer],"configurable": {"recursion_limit": 5}}
        result = parse_agent.invoke({"input": input_prompt},config=config)
        # Try to parse as JSON, fallback to raw output
        try:
            criteria = json.loads(result["output"])
        except:
            criteria = {"raw_output": result["output"]}
        return {"status": "success","agent_thinking": tracer.trace,  # Fixed traces!
        "thinking_steps": len(tracer.trace),
             "criteria": criteria}
    except Exception as e:
        # raise HTTPException(status_code=500, detail=f"Parsing failed: {str(e)}")
        return {
        "status": "error", 
        "agent_thinking": tracer.trace if 'tracer' in locals() else [],
        "error": str(e)
    }


@router.post("/filter-companies")
async def filter_companies(request: dict):
    """Handles ANY input structure → Clean filters"""
    try:
        raw_input = request

        # 🔧 Handle weird nested structure
        if 'additionalProp1' in raw_input:
            user_filters = raw_input['additionalProp1']
        else:
            user_filters = raw_input

        print(f"🔍 Raw input: {raw_input}")
        print(f"🔍 Clean filters: {user_filters}")
        tracer = UITracer()
        config = {"callbacks": [tracer],"configurable": {"recursion_limit": 5}}
        result = filter_agent.invoke({"input": json.dumps(user_filters)}, config=config)

        # Parse result
        try:
            companies = json.loads(result["output"])
        except:
            companies = {"raw_output": result["output"]}

        return {"status": "success","agent_thinking": tracer.trace,  
        "thinking_steps": len(tracer.trace), "companies": companies}
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(500, f"Filtering failed: {str(e)}")


@router.get("/health")
async def health():
    return {"status": "healthy", "agents": "ready"}