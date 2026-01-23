from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
import json
import queue
import asyncio
from pathlib import Path
from datetime import datetime
from langchain_core.callbacks import BaseCallbackHandler
import shutil

from agents.agent1_parse_mandate import create_parse_agent
from agents.agent2_filter_companies import create_filter_agent

router = APIRouter(prefix="/api", tags=["fund-sourcing"])


# ==================================================
# BLOCK-BASED STREAMING CALLBACK
# ==================================================

class BlockStreamingCallback(BaseCallbackHandler):
    """Streams agent thinking in COMPLETE BLOCKS (not tokens)"""

    def __init__(self, event_queue: queue.Queue):
        self.event_queue = event_queue
        self.buffer = ""
        self.in_thought = False
        self.in_action = False
        self.in_action_input = False

    def on_llm_new_token(self, token: str, **kwargs):
        """Buffer tokens until we have a complete block"""
        self.buffer += token

        # Detect and emit COMPLETE blocks
        if "Thought:" in self.buffer and not self.in_thought:
            self.in_thought = True

        if self.in_thought and "Action:" in self.buffer:
            # Extract complete thought
            thought_text = self.buffer.split("Thought:")[-1].split("Action:")[0].strip()
            if thought_text:
                self.event_queue.put({
                    "type": "agent_thinking",
                    "step": "thought",
                    "content": thought_text,
                    "timestamp": datetime.now().isoformat()
                })
            self.in_thought = False
            self.in_action = True

        if self.in_action and "Action Input:" in self.buffer:
            # Extract complete action
            action_text = self.buffer.split("Action:")[-1].split("Action Input:")[0].strip()
            if action_text:
                self.event_queue.put({
                    "type": "agent_thinking",
                    "step": "action",
                    "content": action_text,
                    "timestamp": datetime.now().isoformat()
                })
            self.in_action = False
            self.in_action_input = True

        if self.in_action_input and "\n" in self.buffer.split("Action Input:")[-1]:
            # Extract complete action input (JSON)
            action_input_text = self.buffer.split("Action Input:")[-1].strip()
            if action_input_text:
                self.event_queue.put({
                    "type": "agent_thinking",
                    "step": "action_input",
                    "content": action_input_text,
                    "timestamp": datetime.now().isoformat()
                })
            self.in_action_input = False
            self.buffer = ""

    def on_tool_start(self, serialized: dict, **kwargs):
        """Tool is about to execute"""
        self.event_queue.put({
            "type": "tool_start",
            "tool": serialized.get("name", "unknown"),
            "message": f"Executing: {serialized.get('name', 'unknown')}",
            "timestamp": datetime.now().isoformat()
        })

    def on_llm_end(self, response, **kwargs):
        """Flush any remaining buffer"""
        if self.buffer.strip():
            self.event_queue.put({
                "type": "agent_thinking",
                "step": "final",
                "content": self.buffer.strip(),
                "timestamp": datetime.now().isoformat()
            })
            self.buffer = ""


# ==================================================
# ENDPOINT 1: REST FILE UPLOAD WITH QUERY
# ==================================================

@router.post("/parse-mandate-upload")
async def parse_mandate_upload(file: UploadFile = File(...), query: str = "Generate mandate criteria"):
    """
    Upload PDF file + query via REST
    Saves file and returns filename + query for UI to pass to WebSocket

    curl -X POST http://localhost:8000/api/parse-mandate-upload -F "file=@path/to/file.pdf" -F "query=Your query"

    Returns: {"status": "success", "filename": "...", "query": "...", "message": "..."}
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
            "query": query,
            "message": f"File received: {file.filename}"
        }

    except Exception as e:
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


# ==================================================
# ENDPOINT 2: WEBSOCKET FOR PROCESSING
# ==================================================

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
            "message": "Mandate Parsing Agent initialized",
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
            "message": "Mandate Parsing Agent is analyzing your fund mandate...",
            "timestamp": datetime.now().isoformat()
        })

        try:
            # Create agent
            parse_agent = create_parse_agent()
            input_prompt = f"Scan {pdf_path} Query: {query}"

            # Setup callbacks
            callbacks = [BlockStreamingCallback(event_queue=event_queue)]
            config = {
                "callbacks": callbacks,
                "configurable": {"recursion_limit": 10}
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
                "message": "Mandate Parsing Agent completed analysis!",
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            import traceback
            event_queue.put({
                "type": "analysis_complete",
                "status": "error",
                "error": str(e),
                "message": f"Mandate Parsing Agent failed: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
            print(f"Error: {traceback.format_exc()}")

        # Session end
        event_queue.put({
            "type": "session_complete",
            "status": "success",
            "message": "Mandate Parsing Agent session finished!",
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
            "message": "Sector & Industry Research Agent is initialized",
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
            "message": "Sector & Industry Research Agent is processing your filters...",
            "timestamp": datetime.now().isoformat()
        })

        try:
            # Create filter agent
            filter_agent_with_streaming = create_filter_agent()

            # Setup block streaming callbacks
            callbacks = [BlockStreamingCallback(event_queue=event_queue)]
            config = {
                "callbacks": callbacks,
                "configurable": {"recursion_limit": 10}
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
                "message": f"Sector & Industry Research Agent failed: {str(e)}",
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