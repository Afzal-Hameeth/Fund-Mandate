import json
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import tool
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
import re

load_dotenv()

KEYVAULT_URI = "https://fstodevazureopenai.vault.azure.net/"
credential = DefaultAzureCredential()
kvclient = SecretClient(vault_url=KEYVAULT_URI, credential=credential)

# Retrieve Azure OpenAI configuration from Key Vault
secrets_map = {}
secret_names = ["llm-base-endpoint", "llm-mini", "llm-mini-version", "llm-api-key"]
for secret_name in secret_names:
    try:
        secret = kvclient.get_secret(secret_name)
        secrets_map[secret_name] = secret.value
    except Exception as e:
        print(f"Error retrieving secret '{secret_name}': {e}")
        raise

AZURE_OPENAI_ENDPOINT = secrets_map.get("llm-base-endpoint")
DEPLOYMENT_NAME = secrets_map.get("llm-mini")
OPENAI_API_VERSION = secrets_map.get("llm-mini-version")
GPT5_API_KEY = secrets_map.get("llm-api-key")


# ============================================================================
# CLEAN EVENT STREAMING CALLBACK - MEANINGFUL THOUGHTS ONLY
# ============================================================================

class CleanEventCallback(BaseCallbackHandler):
    """
    Emits meaningful agent thinking and tool invocations without noise.
    Only sends substantial thoughts and tool usage events.
    """

    def __init__(self, event_queue=None):
        self.event_queue = event_queue
        self.buffer = ""
        self.token_count = 0
        self.sentence_endings = {'.', '!', '?'}
        self.semantic_pauses = {',', ':', ';'}

    def is_meaningful_content(self, text: str) -> bool:
        """Validates content is meaningful analysis, not noise or JSON structure"""
        if not text or not text.strip():
            return False

        # Filter out meaningless patterns
        meaningless_patterns = ['||empty||', '....', '----', '====', '****', '||||', '    ', '\n\n\n']

        text_lower = text.lower()
        for pattern in meaningless_patterns:
            if pattern in text_lower:
                return False

        # Filter out JSON structure
        json_char_count = sum(1 for c in text if c in '{}[]:,"')
        total_chars = len(text.strip())
        json_ratio = json_char_count / total_chars if total_chars > 0 else 0

        if json_ratio > 0.3:
            return False

        if any(text.strip().startswith(indicator) for indicator in
               ['{', '[', '"status', '"company_name', '"parameter']):
            return False

        if not any(c.isalpha() for c in text):
            return False

        return True

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Buffers tokens and emits meaningful complete thoughts"""
        self.buffer += token
        self.token_count += 1

        has_sentence_ending = any(ending in self.buffer for ending in self.sentence_endings)
        has_semantic_pause = any(pause in self.buffer for pause in self.semantic_pauses)

        should_emit = False

        if has_sentence_ending and self.token_count >= 50:
            should_emit = True
        elif has_semantic_pause and len(self.buffer.strip()) > 50 and self.token_count >= 50:
            should_emit = True
        elif self.token_count >= 75:
            if self.buffer.strip() and len(self.buffer.strip()) > 50:
                should_emit = True

        if should_emit:
            content = self.buffer.strip()
            if content and self.is_meaningful_content(content):
                if self.event_queue:
                    self.event_queue.put({
                        "type": "agent_thinking",
                        "content": content,
                        "timestamp": datetime.now().isoformat()
                    })
            self.buffer = ""
            self.token_count = 0

    def on_llm_end(self, response, **kwargs) -> None:
        """Flushes remaining meaningful content"""
        content = self.buffer.strip()
        if content and self.is_meaningful_content(content):
            if self.event_queue:
                self.event_queue.put({
                    "type": "agent_thinking",
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                })
        self.buffer = ""
        self.token_count = 0

    def on_agent_action(self, action, **kwargs):
        """Capture agent's tool selection"""
        if self.event_queue:
            self.event_queue.put({
                "type": "agent_thinking",
                "content": f"Using tool: {action.tool}",
                "timestamp": datetime.now().isoformat()
            })

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs):
        """Tool is about to execute - stream immediately for progress"""
        tool_name = serialized.get("name", "unknown")
        print(f"\n[DEBUG] Tool starting: {tool_name}", flush=True)
        if self.event_queue:
            self.event_queue.put({
                "type": "tool_invocation",
                "tool": tool_name,
                "message": f"Invoking {tool_name}...",
                "timestamp": datetime.now().isoformat()
            })


def get_azure_llm(event_queue=None):
    """Initializes Azure OpenAI LLM with streaming enabled"""
    try:
        return AzureChatOpenAI(
            azure_deployment=DEPLOYMENT_NAME,
            openai_api_version=OPENAI_API_VERSION,
            azure_endpoint=AZURE_OPENAI_ENDPOINT,
            api_key=GPT5_API_KEY,
            temperature=1,
            streaming=True,
            callbacks=[CleanEventCallback(event_queue=event_queue)]
        )
    except Exception as e:
        print(f"Error initializing Azure LLM: {str(e)}")
        raise e


print("Authenticating with Azure KeyVault...")
llm = get_azure_llm()
print("Azure OpenAI LLM Initialized")

# ============================================================================
# GLOBAL STATE FOR ANALYSIS WORKFLOW
# ============================================================================

tool_output_capture = {"last_json": None}
event_queue_global = None


def set_event_queue_global(queue):
    """Sets the global event queue for real-time streaming"""
    global event_queue_global
    event_queue_global = queue


# ============================================================================
# RISK ANALYSIS TOOL FOR LANGCHAIN AGENT
# ============================================================================

@tool
def analyze_company_risks(company_name: str, company_risks: str, mandate_risks: str) -> str:
    """
    Analyzes company risks against mandate requirements.
    Uses LLM to evaluate each risk parameter and provide overall investment verdict.

    Returns JSON with per-parameter analysis and overall assessment.
    """

    prompt = ChatPromptTemplate.from_template("""
### System Role

You are a Senior Risk Analyst at a Tier-1 Private Equity firm. Your objective is a strict binary compliance check: Do the identified risks of a target company align with our specific Mandate Requirements?

### Constraints

1. **Scope:** Evaluate ONLY the categories listed in MANDATE REQUIREMENTS.

2. **Exclusion:** If a risk exists in the COMPANY RISKS but is NOT in the MANDATE REQUIREMENTS, ignore it entirely.

3. **Binary Logic:** A parameter is SAFE only if the company risk profile meets or stays within the mandate threshold. Otherwise, it is UNSAFE.

4. **Overall Logic:** The overall status is SAFE if and only if ALL evaluated parameters are SAFE. If one or more fail, the status is UNSAFE.

### Inputs

- **Target Company:** {company_name}

- **Company Risk Profile:** {company_risks}

- **Mandate Requirements:** {mandate_risks}

### Output Instructions

Return a strictly valid JSON object. Do not include markdown formatting, "```json" tags, or any conversational preamble.

### JSON Schema

{{
    "company_name": "{company_name}",
    "parameter_analysis": {{
        "{{Category_Name}}": {{
            "status": "SAFE | UNSAFE",
            "reason": "Max 15 words explaining the specific alignment or breach."
        }}
    }},
    "overall_assessment": {{
        "status": "SAFE | UNSAFE",
        "reason": "Max 20 words summarizing the investment viability based solely on the mandate."
    }}
}}
    """)

    try:
        llm_instance = get_azure_llm(event_queue=event_queue_global)

        response = (prompt | llm_instance).invoke({
            "company_name": company_name,
            "company_risks": company_risks,
            "mandate_risks": mandate_risks
        })

        response_text = response.content if hasattr(response, 'content') else str(response)
        response_text = re.sub(r'```(?:json)?\s*\n?', '', response_text)
        response_text = response_text.strip()

        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            json_str = response_text[start_idx:end_idx + 1]
            result = json.loads(json_str)
        else:
            result = json.loads(response_text)

        required_fields = ['company_name', 'parameter_analysis', 'overall_assessment']
        if not all(k in result for k in required_fields):
            raise ValueError("Missing required fields in response")

        if not isinstance(result['overall_assessment'], dict):
            raise ValueError("overall_assessment must be an object")
        if 'status' not in result['overall_assessment'] or 'reason' not in result['overall_assessment']:
            raise ValueError("overall_assessment must contain status and reason")

        result['company_name'] = company_name
        result['overall_assessment']['status'] = result['overall_assessment']['status'].upper()

        for param, analysis in result.get('parameter_analysis', {}).items():
            if 'status' in analysis:
                analysis['status'] = analysis['status'].upper()

        print(f"\nAnalysis complete for {company_name}")
        print(f"Overall Status: {result['overall_assessment']['status']}")

        tool_output_capture["last_json"] = result
        return json.dumps(result)

    except Exception as e:
        print(f"Error in analyze_company_risks: {str(e)}")
        result = {
            "company_name": company_name,
            "parameter_analysis": {},
            "overall_assessment": {
                "status": "UNSAFE",
                "reason": "Analysis failed due to error"
            }
        }
        tool_output_capture["last_json"] = result
        return json.dumps(result)


# ============================================================================
# LANGCHAIN AGENT SETUP
# ============================================================================

def create_risk_assessment_agent(event_queue=None):
    """Creates a tool-calling agent for risk assessment workflow"""
    tools = [analyze_company_risks]

    agent_prompt = ChatPromptTemplate.from_messages([
        ("system", """Agent Name: risk_assessment_investment_ideas_agent
Description: This agent manages the Risk Assessment of Investment Ideas sub-process within the Research and Idea Generation process for the Fund Mandate capability. It identifies and quantifies potential downsides, including liquidity risk, volatility, and alignment with mandate-specific risk constraints. Trigger this agent to vet proposed investment ideas against risk frameworks before they are finalized in the idea generation phase.

Use the analyze_company_risks tool to evaluate each company.
Provide the tool with the company name, company risks JSON, and mandate requirements JSON."""),
        ("user", "{input}"),
        ("assistant", "{agent_scratchpad}")
    ])

    llm_with_streaming = get_azure_llm(event_queue=event_queue)
    agent = create_tool_calling_agent(llm_with_streaming, tools, agent_prompt)

    # Create callbacks for agent executor (for tool_start, agent_action, etc)
    agent_callbacks = [CleanEventCallback(event_queue=event_queue)]

    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        max_iterations=10,
        handle_parsing_errors=True,
        callbacks=agent_callbacks
    )

    return agent_executor


# ============================================================================
# MAIN ANALYSIS FUNCTION - REAL-TIME EVENT STREAMING
# ============================================================================

def run_risk_assessment_sync(data: Dict[str, Any], event_queue=None) -> List[Dict[str, Any]]:
    """
    Executes risk assessment for multiple companies.
    Streams all events in real-time via event_queue for WebSocket delivery.

    Args:
        data: Contains 'companies' list and 'risk_parameters' dictionary
        event_queue: Queue to put real-time streaming events

    Returns:
        List of analysis results with verdicts for each company
    """
    import queue

    set_event_queue_global(event_queue)

    companies = data.get('companies', [])
    risk_parameters = data.get('risk_parameters', {})

    if not companies:
        raise ValueError("Companies list cannot be empty")
    if not risk_parameters:
        raise ValueError("Risk parameters cannot be empty")

    print(f"\nStarting risk assessment for {len(companies)} companies...")

    if event_queue:
        event_queue.put({
            "type": "session_start",
            "message": "Risk Assessment Agent initialized",
            "companies_count": len(companies),
            "timestamp": datetime.now().isoformat()
        })

    agent_executor = create_risk_assessment_agent(event_queue=event_queue)
    mandate_json = json.dumps(risk_parameters, indent=2)

    all_results = []

    for i, company in enumerate(companies, 1):
        try:
            company_name = company.get('Company') or company.get('Company ') or f'Company_{i}'
            company_risks = company.get('Risks', {})
            company_risks_json = json.dumps(company_risks, indent=2)

            print(f"\nProcessing {company_name}...")

            tool_output_capture["last_json"] = None

            task = f"""
            Analyze the following company against mandate requirements:

            Company Name: {company_name}
            Company Risks: {company_risks_json}
            Mandate Requirements: {mandate_json}

            Use the analyze_company_risks tool to perform the analysis.
            """

            response = agent_executor.invoke({"input": task})

            if tool_output_capture["last_json"]:
                result = tool_output_capture["last_json"]
                all_results.append(result)

                overall_status = result.get('overall_assessment', {}).get('status', 'UNKNOWN')

                print(f"Result for {result['company_name']}: {overall_status}")

                if event_queue:
                    event_queue.put({
                        "type": "analysis_complete",
                        "company_name": result['company_name'],
                        "overall_result": overall_status,
                        "timestamp": datetime.now().isoformat()
                    })
            else:
                raise ValueError("Tool did not produce output")

        except Exception as e:
            print(f"Error processing {company_name}: {str(e)}")
            error_result = {
                "company_name": company_name,
                "overall_assessment": {
                    "status": "UNSAFE",
                    "reason": "Analysis failed"
                },
                "parameter_analysis": {}
            }
            all_results.append(error_result)

            if event_queue:
                event_queue.put({
                    "type": "analysis_complete",
                    "company_name": company_name,
                    "overall_result": "UNSAFE",
                    "timestamp": datetime.now().isoformat()
                })

    print(f"\nRisk Assessment completed for {len(all_results)} companies")

    if event_queue:
        # Transform results to replace overall_assessment with overall_result
        transformed_results = []
        for result in all_results:
            transformed = {
                "company_name": result.get('company_name'),
                "parameter_analysis": result.get('parameter_analysis', {}),
                "overall_result": result.get('overall_assessment', {}).get('status', 'UNKNOWN')
            }
            transformed_results.append(transformed)

        event_queue.put({
            "type": "session_complete",
            "status": "success",
            "message": "Risk Assessment Agent session finished!",
            "companies_analyzed": len(all_results),
            "results": transformed_results,
            "timestamp": datetime.now().isoformat()
        })
        event_queue.put(None)

    return all_results