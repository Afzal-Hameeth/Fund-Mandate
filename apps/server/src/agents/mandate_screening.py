import os
import json
import re
import asyncio
import sys
from io import StringIO
from typing import Optional, List, Any, Dict
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool
from dotenv import load_dotenv
from fastapi import WebSocket
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

load_dotenv()


# KeyVault Configuration
KEY_VAULT_NAME = "fstodevazureopenai"
KEY_VAULT_URL = f"https://{KEY_VAULT_NAME}.vault.azure.net/"

# Secret names in KeyVault
SECRETS_MAP = {
    "api_key": "llm-api-key",
    "endpoint": "llm-base-endpoint",
    "deployment": "llm-41",
    "api_version": "llm-41-version"
}

# Global LLM config
llm_config = None


def get_secrets_from_key_vault():
    """Retrieve LLM secrets from Azure Key Vault"""
    try:

        credential = DefaultAzureCredential()
        kv_client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)

        secrets = {}
        for key, secret_name in SECRETS_MAP.items():
            try:
                secret_value = kv_client.get_secret(secret_name).value
                secrets[key] = secret_value

            except Exception as e:

                raise

        return secrets

    except Exception as e:

        raise


def initialize_azure_llm_config():
    """Initialize Azure OpenAI LLM config for CrewAI"""
    global llm_config

    try:

        secrets = get_secrets_from_key_vault()


        # Set environment variables for litellm/Azure
        os.environ["AZURE_API_KEY"] = secrets['api_key']
        os.environ["AZURE_API_BASE"] = secrets['endpoint']
        os.environ["AZURE_API_VERSION"] = secrets['api_version']

        llm_config = {
            "model": f"azure/{secrets['deployment']}",
            "api_key": secrets['api_key'],
            "api_base": secrets['endpoint'],
            "api_version": secrets['api_version'],
            "temperature": 0.3,
            "max_tokens": 2048
        }


        return llm_config

    except Exception as e:

        raise


# Initialize Azure LLM config
try:
    llm_config = initialize_azure_llm_config()
except Exception as e:

    raise


# ============================================================================
# REAL-TIME OUTPUT STREAMING - CAPTURES AND FORWARDS IN REAL-TIME
# ============================================================================

class RealtimeStreamingWriter:
    """Captures output in real-time and sends to WebSocket"""

    def __init__(self, websocket: WebSocket, original_stdout, event_queue):
        self.websocket = websocket
        self.original_stdout = original_stdout
        self.buffer = ""
        self.event_queue = event_queue
        self.last_thought_sent = False
        self.last_tool_start_sent = False
        self.last_tool_end_sent = False

    def write(self, text: str) -> None:
        """Intercept print statements in real-time"""
        # Always print to terminal
        self.original_stdout.write(text)
        self.original_stdout.flush()

        # Add to buffer
        self.buffer += text

        # Check for specific patterns and queue events
        self._check_and_queue_events(text)

    def _check_and_queue_events(self, text: str) -> None:
        """Check for key patterns and queue events"""
        try:
            # Extract and send THOUGHT in real-time (STEP 2)
            if "Thought:" in text and not self.last_thought_sent:
                thought_match = re.search(r'Thought:?\s*(.+?)(?=Using Tool:|$)', self.buffer, re.DOTALL)
                if thought_match:
                    thought = thought_match.group(1).strip()
                    self.event_queue.append({
                        "type": "step_2",
                        "content": f"💭 STEP 2: Agent Thinking\n\n{thought}"
                    })
                    self.last_thought_sent = True

            # Send TOOL START in real-time (STEP 3)
            if ("Using Tool:" in text or "Executing Tool:" in text) and not self.last_tool_start_sent:
                self.event_queue.append({
                    "type": "step_3",
                    "content": "🔧 STEP 3: Tool Execution Started\n⏳ Executing financial_screening_tool..."
                })
                self.last_tool_start_sent = True

            # Send TOOL COMPLETED in real-time (STEP 4)
            if ("Tool Result:" in text or "Tool Output:" in text) and not self.last_tool_end_sent:
                self.event_queue.append({
                    "type": "step_4",
                    "content": "✅ STEP 4: Tool Completed\n📊 Tool executed successfully"
                })
                self.last_tool_end_sent = True

        except Exception as e:
            raise


    def flush(self) -> None:
        """Flush method for compatibility"""
        self.original_stdout.flush()


# ============================================================================
# ENHANCED WEBSOCKET STREAMING CALLBACK - ALL 7 STEPS
# ============================================================================

class WebSocketStreamingCallback:
    """Custom callback to stream agent events to WebSocket - ALL 7 STEPS"""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.step_count = 0

    async def send_event(self, event_type: str, content: str) -> None:
        """Send event to WebSocket"""
        try:
            self.step_count += 1
            await self.websocket.send_json({
                "type": event_type,
                "content": content,
                "step": self.step_count
            })
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"WebSocket send error: {e}")

    # STEP 1
    async def on_agent_initialized(self) -> None:
        """STEP 1: Called when agent starts"""
        await self.send_event("step_1", "✅ STEP 1: Agent Initialized\n🤖 Financial Screening Specialist agent is ready")

    # STEP 2
    async def on_agent_thinking(self, thought: str) -> None:
        """STEP 2: Called for agent thinking steps"""
        await self.send_event("step_2", f"💭 STEP 2: Agent Thinking\n\n{thought}")

    # STEP 3
    async def on_tool_start(self, tool_name: str) -> None:
        """STEP 3: Called when tool starts"""
        await self.send_event("step_3", f"🔧 STEP 3: Tool Execution Started\n⏳ Executing {tool_name}...")

    # STEP 4
    async def on_tool_end(self, tool_name: str, output: str) -> None:
        """STEP 4: Called when tool finishes"""
        await self.send_event("step_4", f"✅ STEP 4: Tool Completed\n📊 {tool_name} executed successfully")

    # STEP 5
    async def on_screening_progress(self, message: str) -> None:
        """STEP 5: Called during screening progress"""
        await self.send_event("step_5", f"⚙️ STEP 5: Results Processing\n\n{message}")

    # STEP 6
    async def on_agent_finish(self, result: str) -> None:
        """STEP 6: Called when agent finishes"""
        await self.send_event("step_6", f"✨ STEP 6: Agent Task Completed\n\n{result}")

    # STEP 7
    async def on_final_output(self, output: str) -> None:
        """STEP 7: Called with final output"""
        await self.send_event("step_7", f"📋 STEP 7: Final Output Ready\n\n{output}")

    async def on_error(self, error: str) -> None:
        """Called on error"""
        await self.send_event("error", f"⚠️ Error: {error}")


# ============================================================================
# HELPER FUNCTIONS FOR SCREENING - IMPROVED VERSION
# ============================================================================
def parse_constraint(constraint_str: str) -> tuple:
    """Parse constraint - handles both formats"""
    try:
        constraint_str = str(constraint_str).strip()

        # Check if it's a percentage constraint
        is_percentage = '%' in constraint_str

        # Remove currency symbols and labels
        cleaned = re.sub(r'[\$,]', '', constraint_str)
        cleaned = re.sub(r'\s*(USD|M|B|%|Positive)\s*', '', cleaned)

        # Extract operator and number
        match = re.search(r'([><]=?|==|!=)\s*([\d.]+)', cleaned)
        if match:
            operator = match.group(1)
            threshold = float(match.group(2))

            # If it was a percentage constraint, convert to decimal
            if is_percentage and threshold > 1:
                threshold = threshold / 100

            # Convert raw dollars to millions (if threshold > 1000, assume it's in dollars)
            elif threshold > 1000 and not is_percentage:
                threshold = threshold / 1000000  # Convert to millions

            return operator, threshold

        return ">", 0
    except Exception as e:
        print(f"❌ Error parsing constraint '{constraint_str}': {e}")
        return ">", 0


def get_company_value(company: dict, param_name: str) -> Optional[float]:
    """Get numeric value from company - ALL VALUES IN MILLIONS"""
    try:
        param_lower = param_name.lower()

        # Handle NET INCOME
        if param_lower == "net_income":
            net_income = company.get("Net Income")
            if net_income is None:
                return None
            parsed = parse_value(net_income)
            return parsed  # In millions

        # Handle REVENUE - ensure in millions
        if param_lower == "revenue":
            revenue = company.get("Revenue")
            if revenue is None:
                return None
            parsed = parse_value(revenue)
            return parsed  # Already in millions from parse_value

        # Handle MARKET CAP - convert to millions
        if param_lower == "market_cap":
            market_cap = company.get("Market Cap")
            if market_cap is None:
                return None
            parsed = parse_value(market_cap)
            return parsed  # In millions from parse_value

        # Handle EBITDA - convert to percentage of revenue
        if param_lower == "ebitda":
            revenue = company.get("Revenue")
            ebitda_raw = company.get("EBITDA")

            if revenue is None or ebitda_raw is None:
                return None

            ebitda_value = parse_value(ebitda_raw)
            revenue_value = parse_value(revenue)

            if ebitda_value is None or revenue_value is None or revenue_value == 0:
                return None

            # Return as percentage (e.g., 55.6 for 55.6%)
            return (ebitda_value / revenue_value) * 100

        # Handle GROSS PROFIT MARGIN - ensure it's decimal
        if param_lower == "gross_profit_margin":
            gpm = company.get("Gross Profit Margin")
            if gpm is None:
                return None
            parsed = parse_value(gpm)
            # If > 1, assume it's percentage format (e.g., 78.8), convert to decimal (0.788)
            if parsed and parsed > 1:
                return parsed / 100
            return parsed

        # Handle RETURN ON EQUITY - ensure it's decimal
        if param_lower == "return_on_equity":
            roe = company.get("Return on Equity")
            if roe is None:
                return None
            parsed = parse_value(roe)
            # If > 1, assume it's percentage format, convert to decimal
            if parsed and parsed > 1:
                return parsed / 100
            return parsed

        # Standard field mapping
        field_map = {
            "ebitda_margin": ["EBITDA Margin"],
            "growth": ["5-Years Growth", "1-Year Change"],
            "debt_to_equity": ["Debt / Equity"],
            "pe_ratio": ["P/E Ratio"],
            "price_to_book": ["Price/Book"],
            "dividend_yield": ["Dividend Yield"]
        }

        fields = field_map.get(param_lower, [param_name])

        for field in fields:
            if field in company:
                value = company[field]
                if value is None:
                    continue

                parsed = parse_value(value)
                if parsed is not None:
                    # Convert percentages to decimal
                    if isinstance(value, str) and '%' in str(value):
                        return parsed / 100
                    return parsed

        return None
    except Exception as e:
        print(f"Error getting company value for {param_name}: {e}")
        return None


def parse_value(value: Any) -> Optional[float]:
    """Parse various value formats (B, M, T, %)"""
    try:
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            value_str = str(value).strip()
            value_str = value_str.replace("\n", "").replace("%", "").replace("$", "").replace(",", "")

            # Handle B (billions) -> convert to millions
            if 'B' in value_str.upper():
                value_str = value_str.upper().replace('B', '')
                return float(value_str) * 1000

            # Handle M (millions) -> keep as is
            if 'M' in value_str.upper():
                value_str = value_str.upper().replace('M', '')
                return float(value_str)  # Already in millions

            # Handle T (trillions) -> convert to millions
            if 'T' in value_str.upper():
                value_str = value_str.upper().replace('T', '')
                return float(value_str) * 1000000

            if value_str:
                return float(value_str)

        return None
    except Exception:
        return None


def compare_values(actual: float, operator: str, threshold: float) -> bool:
    """Compare actual vs threshold"""
    try:
        if actual is None or threshold is None:
            return False

        # Special handling for "Positive" check (threshold = 0, operator = ">")
        if operator == ">" and threshold == 0:
            return actual > 0

        if operator == ">":
            return actual > threshold
        elif operator == ">=":
            return actual >= threshold
        elif operator == "<":
            return actual < threshold
        elif operator == "<=":
            return actual <= threshold
        elif operator == "==":
            return actual == threshold
        return False
    except Exception as e:
        print(f"Error comparing values: {e}")
        return False


def screen_companies_simple(mandate_parameters: dict, companies: list) -> list:
    """Screen companies against mandate parameters"""
    passed_companies = []

    try:
        if not mandate_parameters or not companies:
            return passed_companies

        for company in companies:
            try:
                # Handle "Company " field with space
                company_name = company.get("Company ", company.get("Company", "Unknown")).strip()
                sector = company.get("Sector", "Unknown").strip()

                all_passed = True
                reasons = []

                for param_name, constraint_str in mandate_parameters.items():
                    operator, threshold = parse_constraint(constraint_str)
                    company_value = get_company_value(company, param_name)

                    if company_value is None:
                        all_passed = False
                        reasons.append(f"{param_name}: N/A ❌")
                        break

                    if compare_values(company_value, operator, threshold):
                        reasons.append(f"{param_name}: {company_value} {operator} {threshold} ✅")
                    else:
                        all_passed = False
                        reasons.append(f"{param_name}: {company_value} {operator} {threshold} ❌")
                        break

                if all_passed:
                    reason_text = " | ".join(reasons)
                    passed_companies.append({
                        "company_name": company_name,
                        "sector": sector,
                        "status": "PASS",
                        "reason": reason_text,
                        "company_details": company
                    })

            except Exception as e:
                print(f"Error screening company: {e}")
                continue

        return passed_companies
    except Exception as e:
        print(f"Error in screen_companies_simple: {e}")
        return []


# ============================================================================
# CUSTOM TOOL: Financial Screening - FIXED
# ============================================================================

class FinancialScreeningTool(BaseTool):
    """Validates companies against mandate parameters"""
    name: str = "financial_screening_tool"
    description: str = """Screen companies against mandate parameters and return only those that pass ALL criteria."""

    def _run(self, mandate_parameters: dict, companies: list) -> str:
        """Screen companies and return passed ones"""
        try:
            print(f"\n🔍 Tool Screening {len(companies)} companies against {len(mandate_parameters)} criteria...")

            if not mandate_parameters or not companies:
                return json.dumps({"company_details": []})

            passed_companies = screen_companies_simple(mandate_parameters, companies)
            print(f"✅ Tool Result: {len(passed_companies)} companies passed")

            company_details_list = []
            for company in passed_companies:
                company_data = company["company_details"].copy()
                company_data["status"] = "Pass"
                company_data["reason"] = company.get("reason", "Meets all criteria")
                company_details_list.append(company_data)

            formatted_response = {"company_details": company_details_list}
            print(f"📊 Tool Output: {len(company_details_list)} qualified companies")
            return json.dumps(formatted_response, default=str)

        except Exception as e:
            print(f"❌ Tool Error: {str(e)}")
            import traceback
            traceback.print_exc()
            return json.dumps({"company_details": []})


# ============================================================================
# CREWAI AGENT
# ============================================================================

try:

    azure_llm = LLM(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=llm_config["api_base"],
        api_version=llm_config["api_version"],
        temperature=llm_config.get("temperature", 0.3),
        max_tokens=llm_config.get("max_tokens", 2048)
    )

    financial_screening_agent = Agent(
        role="Financial Screening Specialist",
        goal="""Evaluate companies against fund mandate parameters.
        Use financial_screening_tool to validate each company.
        Return ONLY valid JSON output with screening results.""",
        backstory="""You are an expert financial analyst specializing in investment screening.
        You have deep knowledge of financial metrics, valuation multiples, and
        institutional investment criteria. You evaluate companies objectively
        against predefined mandate parameters.""",
        llm=azure_llm,
        tools=[FinancialScreeningTool()],
        verbose=True,
        allow_delegation=False
    )
except Exception as e:
    print(f"Agent initialization error: {e}")
    financial_screening_agent = None

# ============================================================================
# CREWAI TASK
# ============================================================================

try:
    screen_companies_task = Task(
        description="""Screen companies against fund mandate parameters.

        Mandate Parameters:
        {mandate_parameters}

        Companies to Screen:
        {companies_list}

        TASK:
        1. Use financial_screening_tool with mandate_parameters and companies_list
        2. Tool returns JSON with ONLY passed companies
        3. Extract results and return as JSON
        4.provide the reason for the particular company why it has passed the screening dynamically according to the threshold comparison against the mandate_parameters.add in the output json in the reason key.

        """,
        expected_output="""Valid JSON array with ONLY passed companies:
        {
            "company_details": [
                {
                    "Company": "company_name",
                    "Country": "country",
                    "Sector": "sector",
                    "status": "Pass",
                    "reason": "{
            "company_details": [
                {
                    "Company": "company_name",
                    "Country": "country",
                    "Sector": "sector",
                    "status": "Pass",
                    "reason": "",
                    ... all metrics given as input
                }
            ]
        }",
                    ... all metrics given as input
                }
            ]
        }""",
        agent=financial_screening_agent
    )
except Exception as e:
    print(f"Task initialization error: {e}")
    screen_companies_task = None

# ============================================================================
# CREWAI CREW
# ============================================================================

try:
    screening_crew = Crew(
        agents=[financial_screening_agent],
        tasks=[screen_companies_task],
        process=Process.sequential,
        verbose=True
    )
except Exception as e:
    print(f"Crew initialization error: {e}")
    screening_crew = None


# ============================================================================
# REAL-TIME WEBSOCKET SCREENING FUNCTION
# ============================================================================

async def run_screening_with_websocket(
        websocket: WebSocket,
        mandate_parameters: dict,
        companies: list
) -> dict:
    """Run screening with REAL-TIME streaming and return company_details"""

    try:
        print("\n" + "=" * 80)
        print("🚀 STARTING SCREENING WORKFLOW")
        print("=" * 80 + "\n")

        callback = WebSocketStreamingCallback(websocket)
        event_queue = []

        # STEP 1: Agent Initialized
        await callback.on_agent_initialized()
        await asyncio.sleep(0.3)

        if not screening_crew:
            print("❌ Screening crew not initialized!")
            await callback.on_error("Screening crew not initialized")
            return {"company_details": []}

        # REDIRECT STDOUT FOR REAL-TIME CAPTURE
        original_stdout = sys.stdout
        streaming_writer = RealtimeStreamingWriter(websocket, original_stdout, event_queue)
        sys.stdout = streaming_writer

        try:
            print("📋 Executing crew with inputs...")

            # Execute crew in thread
            result = await asyncio.to_thread(
                screening_crew.kickoff,
                inputs={
                    "mandate_parameters": mandate_parameters,
                    "companies_list": companies
                }
            )

            print(f"\n✅ Crew execution complete!")
            print(f"Result type: {type(result)}")

        finally:
            # Restore stdout
            sys.stdout = original_stdout

        # Process queued events (STEP 2, 3, 4)
        for event in event_queue:
            await callback.send_event(event["type"], event["content"])
            await asyncio.sleep(0.5)

        result_text = str(result).strip()

        print(f"\n📝 Processing result...")
        print(f"Result length: {len(result_text)} characters")
        print(f"First 300 chars: {result_text[:300]}\n")

        # STEP 5: Results Processed
        await asyncio.sleep(0.5)
        num_companies = len(companies)
        await callback.on_screening_progress(
            f"Total companies evaluated: {num_companies}\n"
            f"Screening criteria applied: {len(mandate_parameters)}"
        )

        # Parse result - IMPROVED JSON EXTRACTION
        parsed_result = {"company_details": []}

        try:
            # Strategy 1: Try direct JSON parsing first
            try:
                raw_parsed = json.loads(result_text)
                if "company_details" in raw_parsed and isinstance(raw_parsed.get("company_details"), list):
                    parsed_result = raw_parsed
                    print(f"✅ Strategy 1 SUCCESS: Direct JSON parsing")
                    print(f"   Found {len(parsed_result['company_details'])} companies\n")
            except json.JSONDecodeError:
                print(f"⚠️ Strategy 1 FAILED: Not valid JSON at root\n")

            # Strategy 2: Extract JSON from wrapped text
            if not parsed_result["company_details"]:
                print(f"Trying Strategy 2: Extract JSON from text...\n")

                # Find all potential JSON objects
                json_matches = re.findall(
                    r'\{[^{}]*"company_details"[^{}]*\}',
                    result_text,
                    re.DOTALL
                )

                if json_matches:
                    print(f"Found {len(json_matches)} JSON matches")

                    # Try the longest match first (most complete)
                    for json_str in sorted(json_matches, key=len, reverse=True):
                        try:
                            raw_parsed = json.loads(json_str)
                            if "company_details" in raw_parsed and isinstance(raw_parsed.get("company_details"), list):
                                parsed_result = raw_parsed
                                print(f"✅ Strategy 2 SUCCESS: Regex extraction")
                                print(f"   Found {len(parsed_result['company_details'])} companies\n")
                                break
                        except json.JSONDecodeError:
                            continue

            # Strategy 3: Extract between first { and last }
            if not parsed_result["company_details"]:
                print(f"Trying Strategy 3: Extract between braces...\n")

                start_idx = result_text.find('{')
                end_idx = result_text.rfind('}') + 1

                if start_idx != -1 and end_idx > start_idx:
                    json_str = result_text[start_idx:end_idx]
                    print(f"Extracted substring length: {len(json_str)}")

                    try:
                        raw_parsed = json.loads(json_str)
                        if "company_details" in raw_parsed and isinstance(raw_parsed.get("company_details"), list):
                            parsed_result = raw_parsed
                            print(f"✅ Strategy 3 SUCCESS: Brace extraction")
                            print(f"   Found {len(parsed_result['company_details'])} companies\n")
                    except json.JSONDecodeError as e:
                        print(f"⚠️ Strategy 3 FAILED: JSON decode error: {e}\n")

                        # Try cleaning the string
                        json_str_clean = json_str.replace('\n', ' ').replace('\\', '')
                        try:
                            raw_parsed = json.loads(json_str_clean)
                            if "company_details" in raw_parsed:
                                parsed_result = raw_parsed
                                print(f"✅ Strategy 3 SUCCESS (after cleaning)")
                                print(f"   Found {len(parsed_result['company_details'])} companies\n")
                        except:
                            pass

        except Exception as e:
            print(f"❌ Error during result parsing: {e}")
            import traceback
            traceback.print_exc()

        # Log final parsing result
        num_qualified = len(parsed_result.get("company_details", []))
        print(f"\n{'=' * 80}")
        print(f"📊 FINAL RESULT: {num_qualified} qualified companies")
        print(f"{'=' * 80}\n")

        # STEP 6: Agent Finish
        await asyncio.sleep(0.5)
        await callback.on_agent_finish(
            f"Screening analysis complete.\n"
            f"Companies qualified: {num_qualified}"
        )

        # STEP 7: Final Output
        await asyncio.sleep(0.5)
        final_json = json.dumps(parsed_result, indent=2, default=str)
        await callback.on_final_output(final_json[:1000])

        print(f"\n✅ Returning parsed result with {num_qualified} companies")
        return parsed_result

    except Exception as e:
        print(f"❌ Error in run_screening_with_websocket: {e}")
        import traceback
        traceback.print_exc()
        await callback.on_error(str(e))
        return {"company_details": []}