from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from agents.risk_agent import run_risk_assessment_sync
import json
import sys
import re
import traceback
from io import StringIO
from datetime import datetime
import os
import asyncio
import queue
import threading
from typing import Callable, List, Dict, Any, AsyncGenerator
from pydantic import BaseModel, ConfigDict


# Request/Response Models
class RiskAnalysisRequest(BaseModel):
    """Risk Analysis Request - Input format from frontend"""
    companies: List[Dict[str, Any]]
    risk_parameters: Dict[str, str]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "companies": [
                    {
                        "Company ": "TestCorp",
                        "Debt / Equity": 0.5,
                        "P/E Ratio": 20,
                        "Return on Equity": 0.15,
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


class RiskAnalysisResponse(BaseModel):
    """Risk Analysis Response"""
    timestamp: str
    status: str
    summary: Dict[str, Any]
    analysis: List[Dict[str, Any]]
    saved_file: str


router = APIRouter(prefix="/risk", tags=["risk-analysis"])


def save_analysis_result(result: Dict[str, Any]) -> str:
    """Save analysis result to JSON file"""
    try:
        filename = f"risk_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w') as f:
            json.dump(result, f, indent=2)

        print(f"✅ Results saved to {filename}")
        return filename
    except Exception as e:
        print(f"❌ Error saving results: {str(e)}")
        return ""


@router.websocket("/analyze")
async def websocket_analyze(websocket: WebSocket):
    """
    ✨ REAL-TIME STREAMING WebSocket ENDPOINT for Risk Analysis ✨

    Single unified endpoint that:
    1. Receives analysis request
    2. Streams events in REAL-TIME as analysis progresses
    3. Returns final JSON results with company verdicts

    ⚡ STREAMING FLOW ⚡
    1. Frontend connects: ws://server/risk/analyze
    2. Frontend sends: {"companies": [...], "risk_parameters": {...}}
    3. Server IMMEDIATELY streams events:
       - session_start: Analysis starting
       - analysis_start: Starting company analysis
       - llm_thinking: LLM processing (real-time)
       - analysis_complete: Company verdict ready
       - session_complete: All done + final JSON results

    ✅ Each event is sent as soon as it's generated - NO DELAYS!

    Example streaming sequence:

    Event 1:
    {
        "type": "session_start",
        "message": "🚀 Starting analysis for 2 companies..."
    }

    Event 2:
    {
        "type": "analysis_start",
        "company": "TestCorp",
        "message": "🔍 Analyzing TestCorp..."
    }

    Event 3:
    {
        "type": "llm_thinking",
        "company": "TestCorp",
        "message": "🧠 LLM analyzing risks for TestCorp..."
    }

    Event 4:
    {
        "type": "analysis_complete",
        "company_name": "TestCorp",
        "overall_status": "UNSAFE",
        "reason": "TestCorp's strong competitive position...",
        "message": "✅ Analysis complete for TestCorp"
    }

    ... (repeat for each company) ...

    Final Event:
    {
        "type": "session_complete",
        "status": "success",
        "message": "✅ Analysis completed for 2 companies",
        "results": [
            {
                "company_name": "TestCorp",
                "overall_status": "UNSAFE",
                "reason": "..."
            },
            {
                "company_name": "FinanceHub Ltd",
                "overall_status": "UNSAFE",
                "reason": "..."
            }
        ]
    }
    """
    await websocket.accept()

    try:
        # Receive the analysis request from frontend
        data_json = await websocket.receive_text()
        data = RiskAnalysisRequest(**json.loads(data_json))

        # Create a queue to receive events from the analysis thread
        event_queue = queue.Queue()

        # Function to run analysis in a separate thread
        def run_analysis_thread():
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

        # Start analysis in background thread
        analysis_thread = threading.Thread(target=run_analysis_thread, daemon=True)
        analysis_thread.start()

        # Stream events from queue to WebSocket in REAL-TIME
        print("🔄 Starting real-time event streaming...")
        while True:
            try:
                # Get event from queue with timeout
                event = event_queue.get(timeout=0.1)

                if event is None:
                    # Sentinel - end of stream
                    print("✅ All events sent, stream complete")
                    break

                # Send event to frontend IMMEDIATELY
                await websocket.send_json(event)
                print(f"📤 Sent event: {event.get('type')}")

                # Small delay to allow client to process
                await asyncio.sleep(0.02)

            except queue.Empty:
                # No event ready yet, continue checking
                continue
            except Exception as e:
                print(f"❌ Error sending event: {e}")
                break

    except WebSocketDisconnect:
        print("🔌 WebSocket disconnected")
    except json.JSONDecodeError as e:
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Invalid JSON format: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
        await websocket.close()
    except Exception as e:
        print(f"❌ WebSocket Error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Server error: {str(e)}",
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
        await websocket.close()


@router.post("/analyze-http")
async def http_analyze(request: RiskAnalysisRequest):
    """
    ✅ HTTP POST ENDPOINT (Alternative to WebSocket)

    For clients that cannot use WebSocket, provides HTTP endpoint.
    Returns all results as JSON immediately (no streaming).

    Request:
    POST /risk/analyze-http
    {
        "companies": [...],
        "risk_parameters": {...}
    }

    Response:
    {
        "status": "success",
        "timestamp": "2026-01-20T...",
        "results": [
            {
                "company_name": "TestCorp",
                "overall_status": "UNSAFE",
                "reason": "..."
            },
            ...
        ]
    }
    """
    try:
        # Run analysis without streaming
        results = await asyncio.to_thread(
            run_risk_assessment_sync,
            {
                "companies": request.companies,
                "risk_parameters": request.risk_parameters
            },
            None  # No event queue
        )

        return {
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "total_companies": len(results),
            "results": results
        }

    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )

