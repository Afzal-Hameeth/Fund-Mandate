from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, Form
import json
import queue
import asyncio
from pathlib import Path
from datetime import datetime
from langchain_core.callbacks import BaseCallbackHandler
import shutil

from agents.agent1_parse_mandate import create_parse_agent
from agents.agent2_filter_companies import create_sector_and_industry_research_agent
from database.repositories.fundRepository import FundMandateRepository

router = APIRouter(prefix="/api", tags=["fund-sourcing"])


class CleanEventCallback(BaseCallbackHandler):
    """Emits tool events + agent thinking without repetition"""

    def __init__(self, event_queue: queue.Queue):
        self.event_queue = event_queue
        self.last_tool = None
        self.thought_emitted = False
        self.thinking_buffer = ""

    def on_llm_new_token(self, token: str, **kwargs):
        """Capture thinking tokens and emit complete thoughts"""
        self.thinking_buffer += token

        # Look for complete Thought: ... Action: pattern
        if "Thought:" in self.thinking_buffer and "Action:" in self.thinking_buffer:
            parts = self.thinking_buffer.split("Thought:")
            if len(parts) > 1:
                thought_part = parts[-1].split("Action:")[0].strip()
                if thought_part and len(thought_part) > 10:  # Substantial thought
                    self.event_queue.put({
                        "type": "agent_thinking",
                        "step": "thought",
                        "content": thought_part,
                        "timestamp": datetime.now().isoformat()
                    })
                    # Clear buffer after emitting
                    self.thinking_buffer = self.thinking_buffer.split("Action:")[1]

    def on_agent_action(self, action, **kwargs):
        """Capture agent's tool selection"""
        if not self.thought_emitted:
            self.event_queue.put({
                "type": "agent_thinking",
                "step": "action",
                "content": f"Using tool: {action.tool}",
                "timestamp": datetime.now().isoformat()
            })
            self.thought_emitted = True

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs):
        """Tool is about to execute"""
        tool_name = serialized.get("name", "unknown")

        self.event_queue.put({
            "type": "tool_start",
            "tool": tool_name,
            "message": f"{tool_name} is processing...",
            "timestamp": datetime.now().isoformat()
        })
        self.last_tool = tool_name

    def on_tool_end(self, output: str, **kwargs):
        """Tool execution complete"""
        tool_name = self.last_tool or "tool"
        self.event_queue.put({
            "type": "tool_end",
            "tool": tool_name,
            "message": f"{tool_name} completed",
            "timestamp": datetime.now().isoformat()
        })
        self.thought_emitted = False
        self.thought_emitted = False


@router.post("/parse-mandate-upload")
async def parse_mandate_upload(
    file: UploadFile = File(...),
    query: str = Form("Generate mandate criteria"),
    fund_name: str = Form(...),
    fund_size: str = Form(...),
    description: str = Form(...)
):
    """
    Upload PDF file + fund details via REST
    Creates database entry for FundMandate and saves file

    Returns: {"status": "success", "mandate_id": 1, "filename": "...", "fund_name": "...", "fund_size": "...", "file_path": "...", "message": "..."}
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    try:
        folder = Path(__file__).parent.parent / "input_fund_mandate"
        folder.mkdir(parents=True, exist_ok=True)

        file_path = folder / file.filename

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Create database entry for FundMandate
        mandate = await FundMandateRepository.create_mandate(
            fund_name=fund_name,
            fund_size=fund_size,
            source_url=str(file_path),
            description=description
        )

        return {
            "status": "success",
            "mandate_id": mandate.id,
            "filename": file.filename,
            "fund_name": mandate.fund_name,
            "fund_size": mandate.fund_size,
            "file_path": str(file_path),
            "query": query,
            "message": f"Fund mandate created and file saved: {file.filename}"
        }

    except Exception as e:
        import traceback
        print(f"Error in parse_mandate_upload: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ==================================================
# ENDPOINT 2: REST FILE UPLOAD (Legacy)
# ==================================================

@router.post("/upload-mandate")
async def upload_mandate(file: UploadFile = File(...)):
    """
    Upload PDF file via REST

    curl -X POST http://localhost:8000/api/upload-mandate -F "file=@path/to/file.pdf"

    Returns: {"status": "success", "filename": "...", "path": "..."}
    """
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files allowed")

    try:
        folder = Path(__file__).parent.parent / "input_fund_mandate"
        folder.mkdir(parents=True, exist_ok=True)

        file_path = folder / file.filename

        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        return {
            "status": "success",
            "filename": file.filename,
            "path": str(file_path),
            "message": f"File saved: {file.filename}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.websocket("/ws/parse-mandate/option2/{session_id}")
async def ws_parse_mandate_option2(websocket: WebSocket, session_id: str):
    """
    OPTION 2: WebSocket processes already-uploaded PDF

    Input (single message):
    {
      "pdf_name": "fund_mandate.pdf",
      "query": "Generate mandate criteria"
    }
    """
    await websocket.accept()

    event_queue = queue.Queue()

    try:
        # Session start
        event_queue.put({
            "type": "session_start",
            "message": "Parsing Agent initialized",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })

        # Background task to stream events
        async def stream_events():
            while True:
                try:
                    event = event_queue.get_nowait()
                    if event is None:
                        break
                    await websocket.send_json(event)
                except queue.Empty:
                    await asyncio.sleep(0.01)

        streaming_task = asyncio.create_task(stream_events())

        # Receive single message with filename + query
        msg = await websocket.receive_json()
        pdf_name = msg.get("pdf_name")
        query = msg.get("query", "Generate mandate criteria")

        if not pdf_name:
            event_queue.put({
                "type": "error",
                "message": "Missing 'pdf_name'",
                "timestamp": datetime.now().isoformat()
            })
            event_queue.put(None)
            await streaming_task
            return

        # Check if file exists
        folder = Path(__file__).parent.parent / "input_fund_mandate"
        pdf_path = folder / pdf_name

        if not pdf_path.exists():
            event_queue.put({
                "type": "error",
                "message": f"File not found: {pdf_name}",
                "timestamp": datetime.now().isoformat()
            })
            event_queue.put(None)
            await streaming_task
            return

        event_queue.put({
            "type": "analysis_start",
            "message": f"File loaded: {pdf_name}",
            "pdf_path": str(pdf_path),
            "timestamp": datetime.now().isoformat()
        })

        event_queue.put({
            "type": "llm_thinking",
            "message": "Parsing Agent is analyzing your fund mandate...",
            "timestamp": datetime.now().isoformat()
        })

        try:
            # Create agent
            parse_agent = create_parse_agent()
            input_prompt = f"Scan {pdf_path} Query: {query}"

            # Setup callbacks
            callbacks = [CleanEventCallback(event_queue=event_queue)]
            config = {
                "callbacks": callbacks,
                "configurable": {"recursion_limit": 50}
            }

            # Execute in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: parse_agent.invoke({"input": input_prompt}, config)
            )

            # Parse result
            try:
                criteria = json.loads(result.get("output", "{}"))
            except:
                criteria = {"raw_output": result.get("output", "")}

            # Send final result
            event_queue.put({
                "type": "analysis_complete",
                "status": "success",
                "criteria": criteria,
                "message": "Parsing Agent completed analysis!",
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            import traceback
            event_queue.put({
                "type": "analysis_complete",
                "status": "error",
                "error": str(e),
                "message": f"Parsing failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            print(f"Error: {traceback.format_exc()}")

        # Session end
        event_queue.put({
            "type": "session_complete",
            "status": "success",
            "message": "Parsing Agent session finished!",
            "timestamp": datetime.now().isoformat()
        })
        event_queue.put(None)

        await streaming_task

    except WebSocketDisconnect:
        print(f"WS disconnected: {session_id}")
    except Exception as e:
        try:
            event_queue.put({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            })
            event_queue.put(None)
        except:
            pass


@router.get("/health/option2")
async def health_option2():
    return {"status": "healthy", "option": "2 - REST Upload + WebSocket"}


# ==================================================
# ENDPOINT 3: WEBSOCKET - FILTER COMPANIES
# ==================================================

@router.websocket("/ws/filter-companies/{session_id}")
async def ws_filter_companies(websocket: WebSocket, session_id: str):
    """
    WebSocket for company filtering with block-based streaming

    Input (single message):
    {
      "additionalProp1": {"geography": "us", "sector": "technology", "industry": "software & IT services"}
    }

    Or direct filters:
    {"geography": "us", "sector": "technology", "industry": "software & IT services"}
    """
    await websocket.accept()

    event_queue = queue.Queue()

    try:
        # Session start
        event_queue.put({
            "type": "session_start",
            "message": "Sector & Industry Research Agent initialized",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })

        # Background task to stream events
        async def stream_events():
            while True:
                try:
                    event = event_queue.get_nowait()
                    if event is None:
                        break
                    await websocket.send_json(event)
                except queue.Empty:
                    await asyncio.sleep(0.01)

        streaming_task = asyncio.create_task(stream_events())

        # Receive filters
        data = await websocket.receive_json()
        user_filters = data

        if not user_filters:
            event_queue.put({
                "type": "error",
                "message": "Filter data is required",
                "timestamp": datetime.now().isoformat()
            })
            event_queue.put(None)
            await streaming_task
            return

        # Session info
        event_queue.put({
            "type": "analysis_start",
            "message": "Filters received and validated",
            "filter_count": len(user_filters),
            "timestamp": datetime.now().isoformat()
        })

        event_queue.put({
            "type": "llm_thinking",
            "message": "Sector & Industry Research Agent is filtering companies...",
            "timestamp": datetime.now().isoformat()
        })

        try:
            # Create filter agent
            filter_agent_with_streaming = create_sector_and_industry_research_agent()

            # Setup block streaming callbacks
            callbacks = [CleanEventCallback(event_queue=event_queue)]
            config = {
                "callbacks": callbacks,
                "configurable": {"recursion_limit": 50}
            }

            # Execute in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: filter_agent_with_streaming.invoke({"input": json.dumps(user_filters)}, config)
            )

            # Parse result safely
            output_str = result.get("output") or "{}"
            try:
                companies = json.loads(output_str)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing JSON from agent output: {e}")
                print(f"Raw output: {output_str}")
                companies = {}

            # Send final result
            event_queue.put({
                "type": "analysis_complete",
                "status": "success",
                "result": companies,
                "companies_count": len(companies.get("qualified", [])) if isinstance(companies, dict) else 0,
                "companies": [c.get("Company ") for c in companies.get("qualified", [])] if isinstance(companies,
                                                                                                       dict) else [],
                "message": f"Sector & Industry Research Agent found {len(companies.get('qualified', []))} matches!",
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            import traceback
            event_queue.put({
                "type": "analysis_complete",
                "status": "error",
                "error": str(e),
                "message": f"❌ Filtering failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            print(f"Error in ws_filter_companies: {traceback.format_exc()}")

        # Session end
        event_queue.put({
            "type": "session_complete",
            "status": "success",
            "message": "Sector & Industry Research Agent session finished!",
            "timestamp": datetime.now().isoformat()
        })
        event_queue.put(None)

        await streaming_task

    except WebSocketDisconnect:
        print(f"WS disconnected: {session_id}")
    except Exception as e:
        try:
            event_queue.put({
                "type": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            })
            event_queue.put(None)
        except:
            pass