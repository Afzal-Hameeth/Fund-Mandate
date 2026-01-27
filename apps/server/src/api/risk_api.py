from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from agents.risk_agent import run_risk_assessment_sync
import json
import queue
import threading
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from pydantic import BaseModel, ConfigDict


class RiskAnalysisRequest(BaseModel):
    """Request model for risk analysis"""
    companies: List[Dict[str, Any]]
    risk_parameters: Dict[str, str]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "companies": [
                    {
                        "Company ": "TestCorp",
                        "Risks": {
                            "Competitive Position": "Strong",
                            "Governance Quality": "Good",
                            "Customer Concentration Risk": "Low",
                            "Vendor / Platform Dependency": "AWS",
                            "Regulatory / Legal Risk": "Low",
                            "Business Model Complexity": "Simple"
                        }
                    }
                ],
                "risk_parameters": {
                    "Competitive Position": "Market leaders",
                    "Governance Quality": "Strong governance",
                    "Customer Concentration Risk": "Diversified",
                    "Vendor / Platform Dependency": "Multi-vendor",
                    "Regulatory / Legal Risk": "Low risk",
                    "Business Model Complexity": "Simple models"
                }
            }
        }
    )


router = APIRouter(prefix="/risk", tags=["risk-analysis"])


# ============================================================================
# WEBSOCKET ENDPOINT FOR REAL-TIME ANALYSIS STREAMING
# ============================================================================

@router.websocket("/analyze")
async def websocket_analyze(websocket: WebSocket):
    """
    Real-time WebSocket endpoint for Risk Assessment of Investment Ideas.

    Receives analysis request and streams all events in real-time:
    - session_start: Analysis session initialized
    - analysis_start: Company analysis started
    - thinking_token: Real-time LLM thinking (streamed as generated)
    - thinking_session_start/end: Thinking block markers
    - parameter_analysis: Individual parameter verdicts
    - analysis_complete: Complete analysis with JSON results
    - session_complete: All companies analyzed with final results

    WebSocket Communication Flow:
    1. Client connects to ws://server/risk/analyze
    2. Client sends: {"companies": [...], "risk_parameters": {...}}
    3. Server processes in background thread
    4. Server streams events as they occur
    5. Client receives thinking tokens in real-time as they are generated
    6. Session ends with final results summary
    """
    await websocket.accept()

    try:
        data_json = await websocket.receive_text()
        data = RiskAnalysisRequest(**json.loads(data_json))

        event_queue = queue.Queue()

        def run_analysis_thread():
            """Runs analysis in background thread to allow async streaming"""
            try:
                run_risk_assessment_sync(
                    {
                        "companies": data.companies,
                        "risk_parameters": data.risk_parameters
                    },
                    event_queue=event_queue
                )
            except Exception as e:
                event_queue.put({
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                event_queue.put(None)

        analysis_thread = threading.Thread(target=run_analysis_thread, daemon=True)
        analysis_thread.start()

        print("Starting real-time event streaming to client...")
        while True:
            try:
                event = event_queue.get(timeout=0.1)

                if event is None:
                    print("Stream complete - all events sent")
                    break

                await websocket.send_json(event)
                print(f"Streamed: {event.get('type')} - {event.get('company_name', event.get('message', ''))}")

                await asyncio.sleep(0.02)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error sending event: {e}")
                break

    except WebSocketDisconnect:
        print("Client disconnected")
    except json.JSONDecodeError as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Invalid JSON: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
        await websocket.close()
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
        await websocket.close()


# ============================================================================
# HTTP ENDPOINT FOR ANALYSIS WITHOUT STREAMING
# ============================================================================

@router.post("/analyze-http")
async def http_analyze(request: RiskAnalysisRequest):
    """
    HTTP POST endpoint for analysis without real-time streaming.
    Returns all results at once after analysis completes.

    Use this endpoint if WebSocket is not available.
    Results are returned as JSON after processing completes.
    """
    try:
        results = await asyncio.to_thread(
            run_risk_assessment_sync,
            {
                "companies": request.companies,
                "risk_parameters": request.risk_parameters
            },
            None
        )

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "total_companies": len(results),
            "results": results
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "timestamp": datetime.now().isoformat()
        }