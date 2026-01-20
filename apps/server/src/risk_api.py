from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from risk_agent import load_data, app as risk_agent_app
import json
import sys
import re
import traceback
from io import StringIO
from datetime import datetime
import os
import asyncio
from typing import Callable, List, Dict, Any
from pydantic import BaseModel


# Request/Response Models
class RiskAnalysisRequest(BaseModel):
    """Risk Analysis Request - Same format as fund_mandate.json"""
    companies: List[Dict[str, Any]]
    risk_parameters: Dict[str, str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "companies": [
                    {
                        "Company ": "SalesForce",
                        "Country": "US",
                        "Sector": "Technology",
                        "Revenue": 34857000000,
                        "Debt / Equity": 0.1938,
                        "P/E Ratio": 34.97,
                        "Return on Equity": 0.1218,
                        "Risks": {
                            "Competitive Position": "Market leader in enterprise CRM",
                            "Governance Quality": "Independent board, SEC-compliant",
                            "Customer Concentration Risk": "Low (no customer >10%)",
                            "Vendor / Platform Dependency": "Uses major cloud providers",
                            "Regulatory / Legal Risk": "Data privacy & antitrust",
                            "Business Model Complexity": "Multi-cloud SaaS"
                        }
                    }
                ],
                "risk_parameters": {
                    "Competitive Position": "Focus on companies with strong or leading positions in their segment",
                    "Governance Quality": "Require robust governance and transparency; avoid weak governance structures",
                    "Customer Concentration Risk": "Prefer companies with diversified customer base; avoid high dependency on single clients",
                    "Vendor / Platform Dependency": "Monitor heavy reliance on third-party cloud or single vendor platforms",
                    "Regulatory / Legal Risk": "Consider exposure to data privacy, antitrust, and compliance regulations",
                    "Business Model Complexity": "Assess complexity of SaaS, multi-platform, or hybrid models; avoid overly complex structures"
                }
            }
        }


class RiskScoreDetail(BaseModel):
    category: str
    score: str
    reason: str
    severity: float


class CompanyRiskDetail(BaseModel):
    company_name: str
    overall_risk_score: float
    risk_scores: List[RiskScoreDetail]
    passes_mandate: bool
    recommendation: str


class RiskAnalysisResponse(BaseModel):
    """Risk Analysis Response"""
    timestamp: str
    summary: Dict[str, Any]
    analysis: List[Dict[str, Any]]
    investable: List[CompanyRiskDetail]
    saved_file: str


router = APIRouter(prefix="/risk", tags=["risk-analysis"])

# # Load default data
# companies, mandate = load_data()


def parse_logs_to_structured(logs: str) -> list:
    """Parse terminal logs into structured JSON format"""
    lines = logs.split('\n')
    structured_logs = []
    
    current_company = None
    in_mandate_section = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # Groq loaded
        if "✅ Groq loaded" in line:
            structured_logs.append({
                "type": "system",
                "message": "Groq LLM loaded successfully",
                "emoji": "✅"
            })
        
        # Companies loaded
        elif "📊" in line and "companies loaded" in line:
            import re
            match = re.search(r'(\d+)\s+companies loaded', line)
            count = match.group(1) if match else "0"
            structured_logs.append({
                "type": "data_load",
                "message": f"{count} companies loaded",
                "count": int(count),
                "emoji": "📊"
            })
        
        # LLM analysis start
        elif "🔍 LLM →" in line:
            company_name = line.replace("🔍 LLM →", "").strip()
            current_company = company_name
            structured_logs.append({
                "type": "company_analysis_start",
                "company_name": company_name,
                "emoji": "🔍"
            })
            in_mandate_section = False
        
        # Mandate comparison section
        elif "📊 MANDATE vs COMPANY:" in line:
            in_mandate_section = True
            structured_logs.append({
                "type": "mandate_comparison_start",
                "company_name": current_company,
                "emoji": "📊"
            })
        
        # Mandate comparison line
        elif in_mandate_section and "•" in line:
            parts = line.split("|")
            if len(parts) >= 2:
                category = parts[0].replace("•", "").strip()
                reason = parts[1].strip() if len(parts) > 1 else ""
                structured_logs.append({
                    "type": "mandate_comparison_detail",
                    "company_name": current_company,
                    "category": category,
                    "reason": reason
                })
        
        # Analysis complete
        elif "✅" in line and "PASS" in line and "/" in line:
            import re
            match = re.search(r'([\d.]+)/10\s*\|\s*Passes:\s*(True|False)', line)
            if match:
                score = float(match.group(1))
                passes = match.group(2) == "True"
                structured_logs.append({
                    "type": "company_analysis_complete",
                    "company_name": current_company,
                    "risk_score": score,
                    "passes_mandate": passes,
                    "emoji": "✅"
                })
            in_mandate_section = False
        
        # Pass mandate summary
        elif "✅" in line and "PASS MANDATE" in line:
            import re
            match = re.search(r'(\d+)/(\d+)', line)
            if match:
                passed = int(match.group(1))
                total = int(match.group(2))
                structured_logs.append({
                    "type": "pass_mandate_summary",
                    "passed": passed,
                    "total": total,
                    "emoji": "✅"
                })
        
        # Investment companies table header
        elif "🏆 INVESTABLE COMPANIES" in line:
            structured_logs.append({
                "type": "investable_companies_start",
                "emoji": "🏆"
            })
        
        # Investment company line (numbered)
        elif line and line[0].isdigit() and "." in line:
            import re
            match = re.search(r'^(\d+)\.\s+(.+?)\s+\|\s+([\d.]+)\s+\|\s+(.+)$', line)
            if match:
                rank = int(match.group(1))
                company = match.group(2).strip()
                score = float(match.group(3))
                recommendation = match.group(4).strip()
                structured_logs.append({
                    "type": "investable_company",
                    "rank": rank,
                    "company_name": company,
                    "risk_score": score,
                    "recommendation": recommendation
                })
        
        # Final pass rate
        elif "📊" in line and "PASS" in line and "%" in line:
            import re
            match = re.search(r'(\d+)/(\d+)\s+\(([0-9.]+)%\)', line)
            if match:
                passed = int(match.group(1))
                total = int(match.group(2))
                percentage = float(match.group(3))
                structured_logs.append({
                    "type": "final_summary",
                    "passed": passed,
                    "total": total,
                    "pass_rate_percent": percentage,
                    "emoji": "📊"
                })
        
        # Results saved
        elif "✅ Results saved to" in line:
            filename = line.replace("✅ Results saved to", "").strip()
            structured_logs.append({
                "type": "results_saved",
                "filename": filename,
                "emoji": "✅"
            })
        
        # Other lines
        elif line and not line.startswith("="):
            structured_logs.append({
                "type": "info",
                "message": line
            })
    
    return structured_logs


class StreamingWriter(StringIO):
    """Custom writer that yields logs as they're written"""
    def __init__(self, callback: Callable = None):
        super().__init__()
        self.callback = callback
        self.lines = []

    def write(self, s: str) -> int:
        result = super().write(s)
        if self.callback and s.strip():
            self.callback(s)
        return result

    def flush(self):
        super().flush()
        if self.callback:
            content = self.getvalue()
            if content:
                self.callback(content)


def save_analysis_result(result, logs):
    """Save analysis result with logs to JSON file"""
    analyses = result.get("analyses", [])
    filtered = result.get("filtered_companies", [])

    analyses_json = []
    for analysis in analyses:
        analyses_json.append({
            "company_name": analysis.company_name,
            "overall_risk_score": analysis.overall_risk_score,
            "risk_scores": [
                {
                    "category": rs.category,
                    "score": rs.score,
                    "reason": rs.reason,
                    "severity": rs.severity
                } for rs in analysis.risk_scores
            ],
            "passes_mandate": analysis.passes_mandate,
            "recommendation": analysis.recommendation
        })

    filtered_json = []
    for analysis in filtered:
        filtered_json.append({
            "company_name": analysis.company_name,
            "overall_risk_score": analysis.overall_risk_score,
            "risk_scores": [
                {
                    "category": rs.category,
                    "score": rs.score,
                    "reason": rs.reason,
                    "severity": rs.severity
                } for rs in analysis.risk_scores
            ],
            "passes_mandate": analysis.passes_mandate,
            "recommendation": analysis.recommendation
        })

    total = len(analyses_json)
    passed = len(filtered_json)

    # Build investment summary table (for display in JSON)
    summary_table = []
    for i, analysis in enumerate(filtered, 1):
        summary_table.append({
            "rank": i,
            "company_name": analysis.company_name,
            "risk_score": analysis.overall_risk_score,
            "recommendation": analysis.recommendation,
            "status": "✅ RECOMMENDED" if analysis.passes_mandate else "⚠️ REVIEW"
        })

    # Create result object with logs
    result_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": round((passed / total * 100) if total > 0 else 0, 1)
        },
        "investment_summary": {
            "title": "🏆 INVESTABLE COMPANIES (LLM w/ MANDATE COMPARISONS)",
            "table": summary_table,
            "total_companies": len(filtered),
            "pass_percentage": round((passed / total * 100) if total > 0 else 0, 1)
        },
        "logs": logs,
        "all_companies": analyses_json,
        "investable_companies": filtered_json
    }

    # Save to file
    filename = f"risk_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(result_data, f, indent=2)

    print(f"✅ Results saved to {filename}")

    return result_data, filename


@router.post('/analyze-custom')
async def analyze_custom(request: RiskAnalysisRequest):
    """
    Run risk agent analysis with custom companies and risk_parameters from frontend
    
    Accepts fund_mandate.json format:
    {
      "companies": [...],
      "risk_parameters": {...}
    }
    """
    try:
        # Validate inputs
        if not request.companies:
            raise HTTPException(status_code=400, detail="companies list cannot be empty")
        if not request.risk_parameters:
            raise HTTPException(status_code=400, detail="risk_parameters cannot be empty")
        
        print(f"\n{'=' * 80}")
        print(f"Risk Analysis Request Received")
        print(f"Companies: {len(request.companies)}")
        print(f"Risk Parameters: {len(request.risk_parameters)}")
        print(f"{'=' * 80}\n")
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()
        
        try:
            # Run analysis with custom data
            result = risk_agent_app.invoke({
                "companies": request.companies,
                "mandate": request.risk_parameters,
                "analyses": [],
                "filtered_companies": []
            })
        finally:
            # Get output and restore stdout
            logs = mystdout.getvalue()
            sys.stdout = old_stdout
        
        # Save results with logs
        result_data, filename = save_analysis_result(result, logs)
        result_data["saved_file"] = filename
        
        print(f"\n✅ Analysis Complete! {result_data['summary']['passed']}/{result_data['summary']['total']} companies passed.\n")
        
        return result_data
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Analysis Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Risk analysis failed: {str(e)}")


@router.post('/analyze-ui')
async def analyze_ui(request: RiskAnalysisRequest):
    """
    Risk Analysis endpoint optimized for Frontend UI
    
    Returns:
    - agent_thinking: List of parsed log events (structured format)
    - summary: Pass/fail statistics
    - analysis: Detailed company risk scores
    - investable: Companies that passed mandate
    - saved_file: Path to saved JSON results
    
    Accepts fund_mandate.json format with companies and risk_parameters fields
    """
    try:
        # Validate inputs
        if not request.companies:
            raise HTTPException(status_code=400, detail="companies list cannot be empty")
        if not request.risk_parameters:
            raise HTTPException(status_code=400, detail="risk_parameters cannot be empty")
        
        print(f"\n{'=' * 80}")
        print(f"🚀 Risk Analysis Started")
        print(f"📊 Companies: {len(request.companies)}")
        print(f"📋 Risk Parameters Categories: {len(request.risk_parameters)}")
        print(f"{'=' * 80}\n")
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()
        
        try:
            # Run analysis with custom data - pass risk_parameters as mandate
            result = risk_agent_app.invoke({
                "companies": request.companies,
                "mandate": request.risk_parameters,
                "analyses": [],
                "filtered_companies": []
            })
        finally:
            # Get output and restore stdout
            logs = mystdout.getvalue()
            sys.stdout = old_stdout
        
        # Parse logs into structured format for UI
        agent_thinking = parse_logs_to_structured(logs)
        
        # Build company analysis list
        analyses = result.get("analyses", [])
        analysis_list = []
        for analysis in analyses:
            analysis_list.append({
                "company_name": analysis.company_name,
                "overall_risk_score": analysis.overall_risk_score,
                "risk_scores": [
                    {
                        "category": rs.category,
                        "score": rs.score,
                        "reason": rs.reason,
                        "severity": rs.severity
                    } for rs in analysis.risk_scores
                ],
                "passes_mandate": analysis.passes_mandate,
                "recommendation": analysis.recommendation
            })
        
        # Build investable companies list
        filtered = result.get("filtered_companies", [])
        investable_list = []
        for analysis in filtered:
            investable_list.append({
                "company_name": analysis.company_name,
                "overall_risk_score": analysis.overall_risk_score,
                "risk_scores": [
                    {
                        "category": rs.category,
                        "score": rs.score,
                        "reason": rs.reason,
                        "severity": rs.severity
                    } for rs in analysis.risk_scores
                ],
                "passes_mandate": analysis.passes_mandate,
                "recommendation": analysis.recommendation
            })
        
        total = len(analysis_list)
        passed = len(investable_list)
        
        # Save results to file
        result_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": round((passed / total * 100) if total > 0 else 0, 1)
            },
            "logs": logs,
            "analysis": analysis_list,
            "investable": investable_list
        }
        
        filename = f"risk_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(result_data, f, indent=2)
        
        print(f"✅ Results saved to {filename}")
        
        # Return UI-optimized response
        return {
            "timestamp": datetime.now().isoformat(),
            "agent_thinking": agent_thinking,  # Structured log events
            "thinking_steps": len(agent_thinking),
            "summary": {
                "total": total,
                "passed": passed,
                "failed": total - passed,
                "pass_rate": round((passed / total * 100) if total > 0 else 0, 1)
            },
            "analysis": analysis_list,
            "investable": investable_list,
            "saved_file": filename,
            "status": "success"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Analysis Error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Risk analysis failed: {str(e)}")


@router.get('/analyze')
async def analyze():
    """Run risk agent analysis"""
    # Capture stdout
    old_stdout = sys.stdout
    sys.stdout = mystdout = StringIO()

    try:
        result = risk_agent_app.invoke({
            "companies": companies,
            "mandate": mandate,
            "analyses": [],
            "filtered_companies": []
        })
    finally:
        # Get output and restore stdout
        logs = mystdout.getvalue()
        sys.stdout = old_stdout

    # Save results with logs (includes summary)
    result_data, filename = save_analysis_result(result, logs)
    
    # Return the complete result_data which already has summary
    result_data["saved_file"] = filename
    return result_data


@router.get('/analyze-stream')
async def analyze_stream():
    """Stream agent analysis with live thinking output"""
    
    # Queue to collect logs as they're written
    log_queue = []
    
    def log_callback(content: str):
        """Called whenever stdout is written to"""
        if content.strip():
            log_queue.append(content)

    async def generate():
        # Capture stdout with streaming callback
        old_stdout = sys.stdout
        streaming_writer = StreamingWriter(callback=log_callback)
        sys.stdout = streaming_writer

        try:
            # Run analysis and yield logs as they come
            result = risk_agent_app.invoke({
                "companies": companies,
                "mandate": mandate,
                "analyses": [],
                "filtered_companies": []
            })
            
            # Flush any remaining output
            streaming_writer.flush()
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
            return
        finally:
            # Restore stdout
            sys.stdout = old_stdout

        # Stream all accumulated logs
        logs = streaming_writer.getvalue()
        if logs.strip():
            yield f"data: {json.dumps({'type': 'log', 'content': logs})}\n\n"
            await asyncio.sleep(0.01)  # Allow browser to render

        # Save results with logs
        try:
            result_data, filename = save_analysis_result(result, logs)
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Save failed: {str(e)}'})}\n\n"
            return

        # Stream final results with complete summary
        result_data["saved_file"] = filename
        yield f"data: {json.dumps({'type': 'complete', 'data': result_data})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
