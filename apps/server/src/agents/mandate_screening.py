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

KEY_VAULT_NAME = "fstodevazureopenai"
KEY_VAULT_URL = f"https://{KEY_VAULT_NAME}.vault.azure.net/"

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
                print(f" Failed to retrieve '{secret_name}': {e}")
                raise

        return secrets

    except Exception as e:
        raise


def initialize_azure_llm_config():
    """Initialize Azure OpenAI LLM config for CrewAI"""
    global llm_config

    try:

        # Get secrets from KeyVault
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


try:
    llm_config = initialize_azure_llm_config()
except Exception as e:

    raise


class RealtimeEventCapture:
    """Capture events in real-time from stdout - THREAD-SAFE VERSION"""

    def __init__(self, original_stdout, callback, loop):
        self.original_stdout = original_stdout
        self.callback = callback
        self.loop = loop
        self.buffer = ""

        # Track what we've already sent - STRICT ORDER
        self.reasoning_sent = False
        self.thought_sent = False
        self.tool_start_sent = False
        self.tool_end_sent = False

    def write(self, text: str) -> None:
        """Write to terminal AND check for events"""
        # Print to terminal immediately
        self.original_stdout.write(text)
        self.original_stdout.flush()

        # Add to buffer
        self.buffer += text

        # Check for events in CORRECT ORDER
        self._check_events_in_order()

    def _clean_text(self, text: str) -> str:
        """Remove non-ASCII characters and special Unicode"""
        cleaned = text.replace('\xa0', ' ')
        cleaned = cleaned.replace('\n', ' ')
        cleaned = cleaned.replace('\r', ' ')
        cleaned = re.sub(r'[^\x20-\x7E]', '', cleaned)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned.strip()

    def _check_events_in_order(self) -> None:
        """Check for events in STRICT ORDER"""
        try:
            #  EVENT 1: Reasoning Plan - Check FIRST
            if ("Reasoning Plan" in self.buffer and
                    not self.reasoning_sent):

                # Look for the entire reasoning block
                reasoning_match = re.search(
                    r'Reasoning Plan(.*?)(?=Agent:|$)',
                    self.buffer,
                    re.DOTALL
                )

                if reasoning_match and not self.reasoning_sent:
                    reasoning_text = "Reasoning Plan" + reasoning_match.group(1)
                    reasoning_text = self._clean_text(reasoning_text)
                    # Optional: keep a tiny sanity check to avoid emitting empty strings
                    if len(reasoning_text) >= 20:
                        self._send_event_safe(self.callback.on_reasoning_plan(reasoning_text))
                        self.reasoning_sent = True

            #  EVENT 2: Agent Thinking - Check SECOND (after reasoning)
            flags = re.IGNORECASE
            if (self.reasoning_sent and
                    "Agent:" in self.buffer and
                    "Thought:" in self.buffer and
                    not self.thought_sent):

                agent_match = re.search(r'Agent:\s*([^\n]+)', self.buffer, flags)
                thought_match = re.search(r'Thought:\s*([^\n]+)', self.buffer, flags)
                action_match = re.search(r'Action:\s*([^\n]+)', self.buffer, flags)  # optional
                using_match = re.search(r'Using\s*Tool:?\s*([^\n]+)', self.buffer, flags)  # optional

                if agent_match and thought_match:
                    agent = self._clean_text(agent_match.group(1))
                    thought = self._clean_text(thought_match.group(1))
                    action = self._clean_text(action_match.group(1)) if action_match else None
                    using_tool = self._clean_text(using_match.group(1)) if using_match else None

                    parts = [f"Agent: {agent}", "", f"Thought: {thought}"]
                    if action:
                        parts += ["", f"Action: {action}"]
                    if using_tool:
                        parts += ["", f"Using Tool: {using_tool}"]

                    thinking_msg = "\n".join(parts)
                    self._send_event_safe(self.callback.on_agent_thinking(thinking_msg))
                    self.thought_sent = True
                    self.original_stdout.write(f"\n✓ [EVENT 2] Agent thinking sent\n")
                    self.original_stdout.flush()

            #  EVENT 3: Tool Start - Check THIRD (after thinking)
            if (self.thought_sent and
                    (
                            "Tool Screening" in self.buffer or "🛠️" in self.buffer or "financial_screening_tool" in self.buffer) and
                    not self.tool_start_sent):
                self._send_event_safe(self.callback.on_tool_start("financial_screening_tool"))
                self.tool_start_sent = True
                self.original_stdout.write(f"\n✓ [EVENT 3] Tool start sent\n")
                self.original_stdout.flush()

            #  EVENT 4: Tool End - Check LAST (after tool starts)
            if (self.tool_start_sent and
                    ("Tool Result:" in self.buffer or "companies passed" in self.buffer.lower()) and
                    not self.tool_end_sent):
                # Try to extract count
                result_match = re.search(r'(\d+)\s*companies?\s*passed', self.buffer, re.IGNORECASE)
                count = result_match.group(1) if result_match else "0"

                self._send_event_safe(self.callback.on_tool_end(
                    "financial_screening_tool",
                    f"{count} companies passed screening"
                ))
                self.tool_end_sent = True
                self.original_stdout.write(f"\n✓ [EVENT 4] Tool end sent\n")
                self.original_stdout.flush()

        except Exception as e:
            self.original_stdout.write(f"\n⚠️ Event capture error: {e}\n")
            self.original_stdout.flush()

    def _send_event_safe(self, coro):
        """Safely send coroutine to event loop from thread"""
        try:
            if self.loop and self.loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, self.loop)
        except Exception as e:
            self.original_stdout.write(f"\n⚠️ Send error: {e}\n")
            self.original_stdout.flush()

    def flush(self) -> None:
        self.original_stdout.flush()

    def get_buffer(self) -> str:
        return self.buffer


class WebSocketStreamingCallback:
    """Stream events to WebSocket with content cleaning"""

    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.step_count = 0

    def _clean_content(self, content: str) -> str:
        """Remove non-ASCII, ANSI codes, and special Unicode characters"""
        # Remove ANSI escape sequences (color codes, formatting)
        ansi_escape_pattern = r'\x1b\[[0-9;]*m|\[0m|\[32m|\[37m'
        cleaned = re.sub(ansi_escape_pattern, '', content)

        # Replace common problematic characters
        cleaned = cleaned.replace('\xa0', ' ')  # Non-breaking space
        cleaned = cleaned.replace('\u200b', '')  # Zero-width space
        cleaned = cleaned.replace('\r', '')  # Carriage return
        cleaned = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', cleaned)
        cleaned = re.sub(r'[^\x20-\x7E\n]', '', cleaned)
        cleaned = re.sub(r'  +', ' ', cleaned)
        cleaned = re.sub(r'\n\n+', '\n', cleaned)

        return cleaned.strip()

    async def send_event(self, event_type: str, content: str) -> None:
        """Send event to WebSocket"""
        try:
            self.step_count += 1
            # Clean content
            cleaned_content = self._clean_content(content)

            message = {
                "type": event_type,
                "content": cleaned_content,
                "step": self.step_count
            }
            print(f"\n[STEP {self.step_count}] Sending: {event_type}")
            await self.websocket.send_json(message)
            await asyncio.sleep(0.3)
        except Exception as e:
            print(f"WebSocket error: {e}")

    async def on_agent_initialized(self) -> None:
        content = """STEP 1: Agent Initialized

 Bottom-Up Fundamental Analysis agent is ready
Initializing screening process..."""
        await self.send_event("step_1", content)

    async def on_reasoning_plan(self, plan: str) -> None:
        content = f"""STEP 2A: Reasoning Plan

{plan}"""
        await self.send_event("step_2a", content)

    async def on_agent_thinking(self, thought: str) -> None:
        content = f"""STEP 2B: Bottom-Up Fundamental Analysis Agent Thinking

{thought}"""
        await self.send_event("step_2b", content)

    async def on_tool_start(self, tool_name: str) -> None:
        content = f"""STEP 3: Tool Execution Started

Executing {tool_name}...
Screening companies against mandate parameters..."""
        await self.send_event("step_3", content)

    async def on_tool_end(self, tool_name: str, output: str) -> None:
        content = f"""STEP 4: Tool Completed

{tool_name} executed successfully
Result: {output}"""
        await self.send_event("step_4", content)

    async def on_screening_progress(self, message: str) -> None:
        content = f"""STEP 5: Results Processing

{message}"""
        await self.send_event("step_5", content)

    async def on_agent_finish(self, result: str) -> None:
        content = f"""STEP 6: Bottom-Up Fundamental Analysis Agent Task Completed

{result}"""
        await self.send_event("step_6", content)

    async def on_final_output(self, output: str) -> None:
        content = f"""STEP 7: Final Output Ready

{output}"""
        await self.send_event("step_7", content)

    async def on_error(self, error: str) -> None:
        await self.send_event("error", f"Error: {error}")


# ============================================================================
# HELPER FUNCTIONS FOR SCREENING
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
        print(f"Error parsing constraint '{constraint_str}': {e}")
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
                        reasons.append(f"{param_name}: N/A ")
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
# CUSTOM TOOL: Financial Screening - NO REASONING
# ============================================================================

class FinancialScreeningTool(BaseTool):
    """Validates companies against mandate parameters - returns ONLY passed companies"""
    name: str = "financial_screening_tool"
    description: str = """Screen companies against mandate parameters and return only those that pass ALL criteria.
    Tool returns ONLY the filtered results - Agent will provide analysis and reasoning."""

    def _run(self, mandate_parameters: dict, companies: list) -> str:
        """Screen companies and return passed ones WITHOUT reasoning"""
        try:
            print(f"\nTool Screening {len(companies)} companies against {len(mandate_parameters)} criteria...")

            if not mandate_parameters or not companies:
                return json.dumps({"company_details": []})

            passed_companies = screen_companies_simple(mandate_parameters, companies)
            print(f"Tool Result: {len(passed_companies)} companies passed")

            company_details_list = []
            for company in passed_companies:
                company_data = company["company_details"].copy()
                company_data["status"] = "Pass"
                company_details_list.append(company_data)

            formatted_response = {"company_details": company_details_list}
            print(f"Tool Output: {len(company_details_list)} qualified companies")
            return json.dumps(formatted_response, default=str)

        except Exception as e:
            print(f"Tool Error: {str(e)}")
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
        goal="""This agent executes the 'Bottom-Up Fundamental Analysis' sub-process as part of the 'Research and Idea Generation process' under the 'Fund Mandate capability'. It focuses on 'granular', 'company-specific evaluation', 'including financial statement analysis', 'earnings modeling', and 'intrinsic valuation'. Use this agent for deep dives into individual securities to determine if they meet the specific criteria of the investment mandate.
        Evaluate companies against fund mandate parameters.
        Use financial_screening_tool to validate each company.
        Return ONLY valid JSON output with screening results.""",
        backstory="""You are an expert financial analyst specializing in investment screening.
        You have deep knowledge of financial metrics, valuation multiples, and
        institutional investment criteria. You evaluate companies objectively
        against predefined mandate parameters.""",
        llm=azure_llm,
        tools=[FinancialScreeningTool()],
        verbose=True,
        reasoning=True,
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
        description="""
        This agent executes the Bottom-Up Fundamental Analysis sub-process as part of the Research and Idea Generation process under the Fund Mandate capability. It focuses on granular, company-specific evaluation, including financial statement analysis, earnings modeling, and intrinsic valuation. Use this agent for deep dives into individual securities to determine if they meet the specific criteria of the investment mandate.
        Screen companies against fund mandate parameters.

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
# RIGID JSON PARSING - HANDLES BACKTICKS & MARKDOWN
# ============================================================================

def extract_and_parse_json(result_text: str) -> dict:
    """
    RIGID JSON PARSING - Handles all formats including backticks
    """
    print(f"\n📝 RIGID JSON PARSING STARTED")
    print(f"Result length: {len(result_text)} chars\n")

    # Strategy 1: Remove markdown backticks first
    print("Strategy 1: Removing markdown backticks...")
    cleaned_text = result_text.strip()

    # Remove ``` json ... ``` wrappers
    if cleaned_text.startswith('```'):
        cleaned_text = re.sub(r'^```(?:json)?\s*', '', cleaned_text)
        cleaned_text = re.sub(r'```\s*$', '', cleaned_text)
        cleaned_text = cleaned_text.strip()
        print("✓ Removed markdown backticks")

    # Strategy 2: Direct JSON parse
    print("Strategy 2: Direct JSON parse...")
    try:
        raw_parsed = json.loads(cleaned_text)
        if "company_details" in raw_parsed and isinstance(raw_parsed.get("company_details"), list):
            print(f"SUCCESS: Direct JSON parse - {len(raw_parsed['company_details'])} companies\n")
            return raw_parsed
    except json.JSONDecodeError as e:
        print(f"Direct JSON failed: {e}\n")

    # Strategy 3: Extract JSON between braces
    print("Strategy 3: Extracting JSON between braces...")
    start = cleaned_text.find('{')
    end = cleaned_text.rfind('}') + 1

    if start != -1 and end > start:
        json_str = cleaned_text[start:end]
        try:
            raw_parsed = json.loads(json_str)
            if "company_details" in raw_parsed and isinstance(raw_parsed.get("company_details"), list):
                print(f"SUCCESS: Brace extraction - {len(raw_parsed['company_details'])} companies\n")
                return raw_parsed
        except json.JSONDecodeError as e:
            print(f"Brace extraction failed: {e}\n")

    # Strategy 4: Look for JSON array
    print("Strategy 4: Extracting JSON array...")
    json_array_match = re.search(r'\[\s*\{.*?\}\s*\]', cleaned_text, re.DOTALL)
    if json_array_match:
        try:
            json_str = json_array_match.group(0)
            companies_array = json.loads(json_str)
            if isinstance(companies_array, list) and len(companies_array) > 0:
                print(f"SUCCESS: Array extraction - {len(companies_array)} companies\n")
                return {"company_details": companies_array}
        except json.JSONDecodeError as e:
            print(f"Array extraction failed: {e}\n")

    # Strategy 5: Remove common problematic characters
    print("Strategy 5: Cleaning problematic characters...")
    cleaned_text = cleaned_text.replace('\n', ' ').replace('\\', '')

    start = cleaned_text.find('{')
    end = cleaned_text.rfind('}') + 1

    if start != -1 and end > start:
        json_str = cleaned_text[start:end]
        try:
            raw_parsed = json.loads(json_str)
            if "company_details" in raw_parsed:
                print(f"SUCCESS: Cleaned extraction - {len(raw_parsed['company_details'])} companies\n")
                return raw_parsed
        except json.JSONDecodeError as e:
            print(f"Cleaned extraction failed: {e}\n")

    print("All parsing strategies failed\n")
    return {"company_details": []}


# ============================================================================
# UPDATED WEBSOCKET SCREENING FUNCTION
# ============================================================================

async def run_screening_with_websocket(
        websocket: WebSocket,
        mandate_parameters: dict,
        companies: list
) -> dict:
    """Run screening with REAL-TIME streaming"""

    try:

        callback = WebSocketStreamingCallback(websocket)

        # STEP 1
        await callback.on_agent_initialized()
        await asyncio.sleep(0.5)

        if not screening_crew:
            await callback.on_error("Screening crew not initialized")
            return {"company_details": []}

        # Get current event loop
        current_loop = asyncio.get_event_loop()

        # Setup REAL-TIME event capture with loop reference
        original_stdout = sys.stdout
        event_capture = RealtimeEventCapture(original_stdout, callback, current_loop)
        sys.stdout = event_capture

        try:
            print("Executing crew with real-time event streaming...\n")

            # Execute crew
            result = await asyncio.to_thread(
                screening_crew.kickoff,
                inputs={
                    "mandate_parameters": mandate_parameters,
                    "companies_list": companies
                }
            )

            print(f"\nCrew execution complete!")

        finally:
            sys.stdout = original_stdout

        # Give time for async events to complete
        await asyncio.sleep(1.5)

        # STEP 5: Results Processing
        num_companies = len(companies)
        await callback.on_screening_progress(
            f"Total companies evaluated: {num_companies}\n"
            f"Screening criteria applied: {len(mandate_parameters)}"
        )

        parsed_result = extract_and_parse_json(str(result).strip())
        num_qualified = len(parsed_result.get("company_details", []))

        await asyncio.sleep(0.5)
        await callback.on_agent_finish(
            f"Screening analysis complete.\nCompanies qualified: {num_qualified}"
        )

        # STEP 7
        await asyncio.sleep(0.5)
        final_json = json.dumps(parsed_result, indent=2, default=str)
        await callback.on_final_output(final_json[:1000])

        return parsed_result

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        await callback.on_error(str(e))
        return {"company_details": []}