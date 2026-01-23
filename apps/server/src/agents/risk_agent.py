import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import tool
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
import re
import sys
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

load_dotenv()

# --- AZURE CONFIG ---
OPENAI_API_VERSION = "2024-12-01-preview"
AZURE_OPENAI_ENDPOINT = "https://stg-secureapi.hexaware.com/api/azureai"
KEYVAULT_URI = "https://kvcapabilitycompass.vault.azure.net/"
SECRET_NAME = "kvCapabilityCompassKeyLLM"
DEPLOYMENT_NAME = "gpt-4o"


# === STREAMING TOKEN CALLBACK ===
class StreamingTokenCallback(BaseCallbackHandler):
    """
    Callback to capture LLM tokens and emit them as meaningful chunks.
    Ensures tokens are only emitted when they form complete thoughts/sentences.
    """

    def __init__(self, event_queue=None):
        self.buffer = ""
        self.event_queue = event_queue
        self.token_count = 0
        # Semantic boundaries where we emit (complete thoughts)
        self.sentence_endings = {'.', '!', '?'}
        self.semantic_pauses = {',', ':', ';'}

    def is_meaningful_content(self, text: str) -> bool:
        """Check if content is meaningful (not just noise or placeholders)"""
        if not text or not text.strip():
            return False

        # Filter out meaningless patterns
        meaningless_patterns = [
            '||empty||',
            '....',
            '----',
            '====',
            '****',
            '||||',
            '    ',  # Just spaces
            '\n\n\n',  # Just newlines
        ]

        text_lower = text.lower()
        for pattern in meaningless_patterns:
            if pattern in text_lower:
                return False

        # Must have at least some alphabetic characters
        if not any(c.isalpha() for c in text):
            return False

        return True

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Capture tokens and emit only on semantic boundaries (complete thoughts)"""
        self.buffer += token
        self.token_count += 1

        # Check for sentence-ending punctuation (strongest signal for complete thought)
        has_sentence_ending = any(ending in self.buffer for ending in self.sentence_endings)

        # Check for semantic pause followed by substantial content
        has_semantic_pause = any(pause in self.buffer for pause in self.semantic_pauses)

        # Emit ONLY when we have meaningful, complete content
        should_emit = False

        if has_sentence_ending:
            # Complete sentence - definitely emit
            should_emit = True
        elif has_semantic_pause and len(self.buffer.strip()) > 20:
            # Meaningful pause with good chunk size
            should_emit = True
        elif self.token_count >= 50:
            # Fallback: if buffer gets too large, emit to avoid memory issues
            # But only if it has meaningful content (not just whitespace)
            if self.buffer.strip() and len(self.buffer.strip()) > 15:
                should_emit = True

        if should_emit:
            content = self.buffer.strip()
            # ✅ Only emit if content is meaningful (not noise/placeholders)
            if content and self.is_meaningful_content(content):
                if self.event_queue:
                    self.event_queue.put({
                        "type": "thinking_token",
                        "content": content,
                        "timestamp": __import__("datetime").datetime.now().isoformat()
                    })
                print(content, end="", flush=True)
            self.buffer = ""
            self.token_count = 0

    def on_llm_end(self, response, **kwargs) -> None:
        """Flush any remaining meaningful content when LLM finishes"""
        content = self.buffer.strip()
        # ✅ Only emit if content is meaningful (not noise/placeholders)
        if content and self.is_meaningful_content(content):
            if self.event_queue:
                self.event_queue.put({
                    "type": "thinking_token",
                    "content": content,
                    "timestamp": __import__("datetime").datetime.now().isoformat()
                })
            print(content, end="", flush=True)
        self.buffer = ""
        self.token_count = 0


def get_azure_llm(event_queue=None):
    """Initialize Azure OpenAI LLM with KeyVault authentication and streaming"""
    try:
        credential = DefaultAzureCredential()
        kvclient = SecretClient(vault_url=KEYVAULT_URI, credential=credential)
        api_key = kvclient.get_secret(SECRET_NAME).value
        return AzureChatOpenAI(
            azure_deployment=DEPLOYMENT_NAME,
            openai_api_version=OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=api_key,
            temperature=0.0,  # ✅ Deterministic
            streaming=True,  # ✅ Enable streaming
            callbacks=[StreamingTokenCallback(event_queue=event_queue)]
        )
    except Exception as e:
        print(f"❌ Failed to initialize Azure LLM: {str(e)}")
        raise e

llm = get_azure_llm()


class RiskAssessment(BaseModel):
    category: str = Field(description="Risk category name")
    status: str = Field(description="Safe or Unsafe")
    reason: str = Field(description="Explanation for the assessment")


class CompanyRiskAnalysis(BaseModel):
    company_name: str = Field(description="Name of the company")
    overall_status: str = Field(description="Overall Safe or Unsafe")
    risk_assessments: List[RiskAssessment] = Field(description="Individual risk category assessments")
    recommendation: str = Field(description="Investment recommendation")


# === GLOBAL VARIABLES FOR STREAMING ===
tool_output_capture = {"last_json": None}
stream_callback = None  # Function to call for streaming events


def set_stream_callback(callback):
    """Set the callback function for streaming events"""
    global stream_callback
    stream_callback = callback


def emit_event(event_type: str, **kwargs):
    """Emit a streaming event if callback is set"""
    global stream_callback
    if stream_callback:
        event = {
            "type": event_type,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            **kwargs
        }
        stream_callback(event)


# === TOOLS FOR LANGCHAIN AGENT ===

@tool
def analyze_company_risks(company_name: str, company_risks: str, mandate_risks: str) -> str:
    """
    Analyze company risks against mandate risk parameters.
    Provides detailed analysis per parameter + overall verdict.

    Args:
        company_name: Name of the company
        company_risks: JSON string of company risks
        mandate_risks: JSON string of mandate risk parameters (variable categories)

    Returns:
        JSON string with per-parameter analysis + overall verdict
    """

    prompt = ChatPromptTemplate.from_template("""
    You are a financial risk analyst. Analyze the company risks against mandate requirements in detail.

    CRITICAL: Analyze ONLY the parameters specified in MANDATE REQUIREMENTS, not all possible categories.

    COMPANY: {company_name}
    COMPANY RISKS: {company_risks}
    MANDATE REQUIREMENTS (analyze ONLY these): {mandate_risks}

    Task:
    1. For EACH risk category in the MANDATE REQUIREMENTS (and ONLY those):
       - Check if company's risk doesnt affect the mandate requirement
       - Assess if company meets the requirement (SAFE) or fails it (UNSAFE)
       - Provide a crisp, short reason (1 sentence max, 40-50 words)

    2. Then provide OVERALL assessment:
       - Overall status: SAFE (all mandate categories pass) or UNSAFE (any mandate category fails)
       - Overall reason: One catchy, compelling sentence (40-50 words)
       - Only consider MANDATE parameters in this assessment

    IMPORTANT: Ignore any company risk categories not in the mandate.

    Return ONLY valid JSON (no markdown, no explanation):
    {{
        "company_name": "{company_name}",
        "parameter_analysis": {{
            "Category_Name_1": {{
                "status": "SAFE or UNSAFE",
                "reason": "Crisp reason why (max 40 words)"
            }},
            "Category_Name_2": {{
                "status": "SAFE or UNSAFE",
                "reason": "Crisp reason why (max 40 words)"
            }}
        }},
        "overall_status": "SAFE or UNSAFE",
        "overall_reason": "One catchy sentence explaining overall verdict (40-50 words)"
    }}
    """)

    try:
        llm_instance = get_azure_llm()

        response = (prompt | llm_instance).invoke({
            "company_name": company_name,
            "company_risks": company_risks,
            "mandate_risks": mandate_risks
        })

        # Extract JSON from response
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Clean up markdown if present
        response_text = re.sub(r'```(?:json)?\s*\n?', '', response_text)
        response_text = response_text.strip()

        # Find first { and last } to extract complete JSON
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = response_text[start_idx:end_idx + 1]
            result = json.loads(json_str)
        else:
            result = json.loads(response_text)

        # Validate required fields
        required_fields = ['company_name', 'parameter_analysis', 'overall_status', 'overall_reason']
        if not all(k in result for k in required_fields):
            raise ValueError("Missing required fields")

        # FORCE COMPANY NAME FROM INPUT (not from LLM output)
        # This ensures we always use the actual company name from JSON input
        result['company_name'] = company_name

        # Ensure status is uppercase
        result['overall_status'] = result['overall_status'].upper()

        # Ensure all parameter statuses are uppercase
        for param, analysis in result.get('parameter_analysis', {}).items():
            if 'status' in analysis:
                analysis['status'] = analysis['status'].upper()

        print(f"\n✅ Successfully analyzed {company_name}")
        print(f"   JSON captured: {json.dumps(result, indent=2)}")

        # 🔥 CAPTURE THE JSON OUTPUT GLOBALLY 🔥
        tool_output_capture["last_json"] = result

        return json.dumps(result)

    except Exception as e:
        print(f"❌ Error in analyze_company_risks: {str(e)}")
        result = {
            "company_name": company_name,
            "parameter_analysis": {},
            "overall_status": "UNSAFE",
            "overall_reason": "Analysis failed due to processing error"
        }
        tool_output_capture["last_json"] = result
        return json.dumps(result)


# === AGENT SETUP ===
def create_risk_assessment_agent(event_queue=None):
    """
    Create a tool-calling agent for risk assessment.
    Agent will use the analyze_company_risks tool to perform analysis.
    """
    # Define tools list
    tools = [analyze_company_risks]

    # Create agent prompt with required variables
    agent_prompt = ChatPromptTemplate.from_messages([
        ("system", """This agent manages the Risk Assessment of Investment Ideas sub-process within the Research and Idea Generation process for the Fund Mandate capability. 
        It identifies and quantifies potential downsides, including liquidity risk, volatility, and alignment with mandate-specific risk constraints. 
        Trigger this agent to vet proposed investment ideas against risk frameworks before they are finalized in the idea generation phase.

Use the analyze_company_risks tool to evaluate each company.
Provide the tool with the company name, company risks JSON, and mandate requirements JSON."""),
        ("user", "{input}"),
        ("assistant", "{agent_scratchpad}")
    ])

    # Create the agent using tool-calling approach with streaming LLM
    llm_with_streaming = get_azure_llm(event_queue=event_queue)
    agent = create_tool_calling_agent(llm_with_streaming, tools, agent_prompt)

    # Create agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True
    )

    return agent_executor


def run_risk_assessment_sync(data: Dict[str, Any], event_queue=None) -> List[Dict[str, Any]]:
    """
    Run risk assessment on companies using the agent and tool approach.
    Streams events in REAL-TIME via event queue.

    Args:
        data: Dictionary containing:
            - companies: List of company dictionaries with Company and Risks
            - risk_parameters: Dictionary of mandate risk parameters
        event_queue: Optional queue to put streaming events (for real-time sending)

    Returns:
        List of dictionaries with: {company_name, overall_status, reason}
    """
    import queue

    companies = data.get('companies', [])
    risk_parameters = data.get('risk_parameters', {})

    if not companies:
        raise ValueError("❌ Companies list cannot be empty")
    if not risk_parameters:
        raise ValueError("❌ Risk parameters cannot be empty")

    print(f"\n📊 Starting risk assessment for {len(companies)} companies...")

    # Put session start event in queue IMMEDIATELY
    if event_queue:
        event_queue.put({
            "type": "session_start",
            "message": f" Starting Risk Assessment of Investment Ideas for {len(companies)} companies...",
            "companies_count": len(companies)
        })

    # Create agent (with event_queue for streaming)
    agent_executor = create_risk_assessment_agent(event_queue=event_queue)

    # Prepare mandate as JSON string
    mandate_json = json.dumps(risk_parameters, indent=2)

    all_results = []

    # Process each company through the agent
    for i, company in enumerate(companies, 1):
        try:
            # Handle both 'Company' and 'Company ' keys (with or without trailing space)
            company_name = company.get('Company') or company.get('Company ') or f'Company_{i}'
            company_risks = company.get('Risks', {})
            company_risks_json = json.dumps(company_risks, indent=2)

            print(f"\n▶️  Processing {company_name}...")

            # Put analysis start event IMMEDIATELY
            if event_queue:
                event_queue.put({
                    "type": "analysis_start",
                    "company": company_name,
                    "message": f" Analyzing {company_name}...",
                    "timestamp": __import__("datetime").datetime.now().isoformat()
                })

            # Reset capture for this company
            tool_output_capture["last_json"] = None

            # Create task for agent
            task = f"""
            Analyze the following company against mandate requirements:

            Company Name: {company_name}
            Company Risks: {company_risks_json}
            Mandate Requirements: {mandate_json}

            Use the analyze_company_risks tool to perform the analysis.
            """

            # Put thinking event IMMEDIATELY
            if event_queue:
                event_queue.put({
                    "type": "llm_thinking",
                    "company": company_name,
                    "message": f" LLM analyzing risks for {company_name}...",
                    "timestamp": __import__("datetime").datetime.now().isoformat()
                })

            # Invoke agent (agent will call the tool internally)
            response = agent_executor.invoke({"input": task})

            # ✅ GET JSON FROM CAPTURED TOOL OUTPUT (not from agent response)
            if tool_output_capture["last_json"]:
                result = tool_output_capture["last_json"]
                all_results.append(result)

                print(f"   ✅ {result['company_name']}: {result['overall_status']}")

                # Stream parameter analysis events
                for param_name, param_analysis in result.get('parameter_analysis', {}).items():
                    if event_queue:
                        event_queue.put({
                            "type": "parameter_analysis",
                            "company_name": result['company_name'],
                            "parameter": param_name,
                            "status": param_analysis.get('status', 'UNKNOWN'),
                            "reason": param_analysis.get('reason', ''),
                            "timestamp": __import__("datetime").datetime.now().isoformat()
                        })
                        print(f"      • {param_name}: {param_analysis.get('status')} - {param_analysis.get('reason')}")

                # Put analysis complete event with overall verdict
                if event_queue:
                    event_queue.put({
                        "type": "analysis_complete",
                        "company_name": result['company_name'],
                        "overall_status": result['overall_status'],
                        "overall_reason": result.get('overall_reason', ''),
                        "parameter_analysis": result.get('parameter_analysis', {}),
                        "message": f"Risk Assessment of Investment Ideas Analysis complete for {result['company_name']}",
                        "timestamp": __import__("datetime").datetime.now().isoformat()
                    })
                    print(f"   → Overall: {result.get('overall_reason', '')}")
            else:
                # Fallback if capture didn't work
                raise ValueError("Tool did not produce JSON output")

        except Exception as e:
            print(f" Error processing {company_name}: {str(e)}")
            all_results.append({
                "company_name": company_name,
                "overall_status": "UNSAFE",
                "reason": f"Analysis failed"
            })

    print(f"\n✅ Risk assessment completed for {len(all_results)} companies")

    # Put session complete event with FINAL RESULTS
    if event_queue:
        event_queue.put({
            "type": "session_complete",
            "status": "success",
            "message": f"Risk Assessment of Investment Ideas completed for {len(all_results)} companies",
            "results": all_results,
            "timestamp": __import__("datetime").datetime.now().isoformat()
        })
        event_queue.put(None)  # Sentinel to indicate end of stream

    return all_results

# === API USAGE ONLY ===
# This module is designed to be used via the FastAPI WebSocket endpoint
#
# WebSocket endpoint: ws://localhost:8000/risk/analyze
#
# Send a JSON request with:
# {
#     "companies": [
#         {
#             "Company ": "Company Name",
#             "Risks": {
#                 "Competitive Position": "description",
#                 "Governance Quality": "description",
#                 "Customer Concentration Risk": "description",
#                 "Vendor / Platform Dependency": "description",
#                 "Regulatory / Legal Risk": "description",
#                 "Business Model Complexity": "description"
#             }
#         }
#     ],
#     "risk_parameters": {
#         "Competitive Position": "mandate requirement",
#         "Governance Quality": "mandate requirement",
#         "Customer Concentration Risk": "mandate requirement",
#         "Vendor / Platform Dependency": "mandate requirement",
#         "Regulatory / Legal Risk": "mandate requirement",
#         "Business Model Complexity": "mandate requirement"
#     }
# }
#
# The endpoint will stream events in real-time:
# - session_start: Analysis starting
# - analysis_start: Per company
# - llm_thinking: LLM processing started
# - thinking_token: Real-time LLM thinking (actual agent reasoning)
# - analysis_complete: Verdict ready for company
# - session_complete: All done with final JSON results