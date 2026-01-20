import os
import json
import re
import litellm
from typing import Optional, List
from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

load_dotenv()

# ============================================================================
# AZURE LLM CONFIGURATION FROM KEYVAULT
# ============================================================================

print("\n" + "=" * 80)
print("🔑 AZURE LLM INITIALIZATION FROM KEYVAULT")
print("=" * 80 + "\n")

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
        print(f"🔐 Connecting to KeyVault: {KEY_VAULT_NAME}")

        credential = DefaultAzureCredential()
        kv_client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)

        secrets = {}
        for key, secret_name in SECRETS_MAP.items():
            try:
                secret_value = kv_client.get_secret(secret_name).value
                secrets[key] = secret_value
                print(f"  ✓ Retrieved secret: {secret_name}")
            except Exception as e:
                print(f"  ❌ Failed to retrieve '{secret_name}': {e}")
                raise

        return secrets

    except Exception as e:
        print(f"❌ KeyVault authentication failed: {e}")
        print("   Ensure you're logged in with: az login")
        raise


def initialize_azure_llm_config():
    """Initialize Azure OpenAI LLM config for CrewAI"""
    global llm_config

    try:
        print(f"\nVault Name: {KEY_VAULT_NAME}\n")

        # Get secrets from KeyVault
        secrets = get_secrets_from_key_vault()

        print(f"\n✓ All secrets retrieved successfully:")
        print(f"  - Endpoint: {secrets['endpoint'][:60]}...")
        print(f"  - Deployment: {secrets['deployment']}")
        print(f"  - API Version: {secrets['api_version']}")
        print(f"  - API Key: {secrets['api_key'][:20]}...\n")

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

        print("✅ Azure LLM configuration initialized successfully")
        print(f"   Model: azure/{secrets['deployment']}")
        print(f"   Endpoint: {secrets['endpoint'][:50]}...")
        print("=" * 80 + "\n")

        return llm_config

    except Exception as e:
        print(f"❌ LLM configuration failed: {e}")
        print("=" * 80 + "\n")
        raise


# Initialize Azure LLM config
try:
    llm_config = initialize_azure_llm_config()
except Exception as e:
    print(f"❌ Failed to initialize Azure LLM: {e}")
    raise


# ============================================================================
# HELPER FUNCTIONS FOR SCREENING
# ============================================================================

def parse_constraint(constraint_str: str) -> tuple:
    """Parse "> 40000000" into (">", 40000000)"""
    try:
        match = re.search(r'([><]=?|==|!=)\s*([\d.]+)', str(constraint_str))
        if match:
            operator = match.group(1)
            threshold = float(match.group(2))
            return operator, threshold
        return ">", 0
    except Exception as e:
        print(f"Error parsing constraint: {e}")
        return ">", 0


def get_company_value(company: dict, param_name: str) -> Optional[float]:
    """Get numeric value from company for parameter"""
    try:
        field_map = {
            "revenue": ["Revenue"],
            "ebitda": ["EBITDA"],
            "ebitda_margin": ["EBITDA Margin"],
            "growth": ["5-Years Growth", "1-Year Change"],
            "net_income": ["Net Income"],
            "debt_to_equity": ["Debt / Equity"],
            "pe_ratio": ["P/E Ratio"],
            "price_to_book": ["Price/Book"],
            "market_cap": ["Market Cap"],
            "gross_profit_margin": ["Gross Profit Margin"],
            "return_on_equity": ["Return on Equity"],
            "dividend_yield": ["Dividend Yield"]
        }

        fields = field_map.get(param_name.lower(), [param_name])

        for field in fields:
            if field in company:
                value = company[field]
                if value is None:
                    continue
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    cleaned = re.sub(r'[^0-9.-]', '', str(value))
                    try:
                        return float(cleaned) if cleaned else None
                    except:
                        continue
        return None
    except Exception as e:
        print(f"Error getting company value for {param_name}: {e}")
        return None


def compare_values(actual: float, operator: str, threshold: float) -> bool:
    """Compare actual vs threshold"""
    try:
        if actual is None or threshold is None:
            return False

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
                company_name = company.get("Company", company.get("company_name", "Unknown"))
                sector = company.get("Sector", company.get("sector", "Unknown"))

                all_passed = True
                reason_parts = []

                for param_name, constraint_str in mandate_parameters.items():
                    operator, threshold = parse_constraint(constraint_str)
                    company_value = get_company_value(company, param_name)

                    if company_value is None:
                        all_passed = False
                        reason_parts.append(f"{param_name}: N/A ❌")
                        break

                    comparison_result = compare_values(company_value, operator, threshold)

                    if comparison_result:
                        reason_parts.append(f"{param_name}: {company_value} {operator} {threshold} ✅")
                    else:
                        all_passed = False
                        reason_parts.append(f"{param_name}: {company_value} {operator} {threshold} ❌")
                        break

                if all_passed:
                    reason = " | ".join(reason_parts)
                    passed_companies.append({
                        "company_name": company_name,
                        "sector": sector,
                        "status": "PASS",
                        "reason": reason,
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
# CUSTOM TOOL: Financial Screening
# ============================================================================

class FinancialScreeningTool(BaseTool):
    """Validates companies against mandate parameters"""
    name: str = "financial_screening_tool"
    description: str = """Screen companies against mandate parameters and return only those that pass ALL criteria."""

    def _run(self, mandate_parameters: dict, companies: list) -> str:
        """Screen companies"""
        try:
            print(f"\n🛠️  TOOL EXECUTING: financial_screening_tool")
            print(f"📋 Screening {len(companies)} companies against {len(mandate_parameters)} criteria\n")

            if not mandate_parameters or not companies:
                return json.dumps({"company_details": []})

            passed_companies = screen_companies_simple(mandate_parameters, companies)

            print(f"\n✅ TOOL RESULT: {len(passed_companies)} companies passed\n")

            company_details_list = []
            for company in passed_companies:
                company_data = company["company_details"].copy()
                company_data["status"] = "Pass"
                company_data["reason"] = company.get("reason", "")
                company_details_list.append(company_data)

            return json.dumps({"company_details": company_details_list}, default=str)

        except Exception as e:
            print(f"❌ Tool Error: {str(e)}")
            return json.dumps({"company_details": []})


# ============================================================================
# CREWAI AGENT SETUP - Uses Azure LLM via litellm
# ============================================================================

try:
    # Create a custom LLM class that wraps litellm
    from crewai import LLM

    # Use litellm directly with Azure config from KeyVault
    azure_llm = LLM(
        model=llm_config["model"],
        api_key=llm_config["api_key"],
        base_url=llm_config["api_base"],
        api_version=llm_config["api_version"],
    )

    print(f"✅ Azure LLM created: {llm_config['model']}")

    financial_screening_agent = Agent(
        role="Financial Screening Specialist",
        goal="""Evaluate companies against fund mandate parameters.
        Use financial_screening_tool to validate each company.
        Return ONLY valid JSON output with screening results.""",
        backstory="""You are an expert financial analyst specializing in investment screening.
        You have deep knowledge of financial metrics, valuation multiples, and
        institutional investment criteria. You evaluate companies objectively
        against predefined mandate parameters. Think through each decision carefully.""",
        tools=[FinancialScreeningTool()],
        verbose=True,
        allow_delegation=False,
        llm=azure_llm
    )
    print("✅ Agent initialized successfully\n")
except Exception as e:
    print(f"❌ Agent initialization error: {e}")
    import traceback

    traceback.print_exc()
    financial_screening_agent = None

# ============================================================================
# CREWAI TASK
# ============================================================================

try:
    if financial_screening_agent:
        screen_companies_task = Task(
            description="""Screen companies against fund mandate parameters.

            Mandate Parameters:
            {mandate_parameters}

            Companies to Screen:
            {companies_list}

            TASK:
            1. Analyze each company carefully against the mandate parameters
            2. Use financial_screening_tool to perform screening
            3. Tool returns JSON with ONLY passed companies
            4. Provide the reason why each company passed
            5. Think through the screening logic step by step

            OUTPUT FORMAT (STRICT JSON):
            {
                "company_details": [
                    {
                        "Company": "company_name",
                        "Country": "country",
                        "Sector": "sector",
                        "status": "Pass",
                        "reason": "reason it has passed with metric comparisons",
                        ... all financial metrics
                    }
                ]
            }
            """,
            expected_output="""Valid JSON with ONLY passed companies.""",
            agent=financial_screening_agent
        )
        print("✅ Task initialized successfully\n")
    else:
        screen_companies_task = None
except Exception as e:
    print(f"❌ Task initialization error: {e}")
    import traceback

    traceback.print_exc()
    screen_companies_task = None

# ============================================================================
# CREWAI CREW
# ============================================================================

try:
    if financial_screening_agent and screen_companies_task:
        screening_crew = Crew(
            agents=[financial_screening_agent],
            tasks=[screen_companies_task],
            process=Process.sequential,
            verbose=True
        )
        print("✅ Screening Crew initialized successfully\n")
    else:
        screening_crew = None
except Exception as e:
    print(f"❌ Crew initialization error: {e}")
    import traceback

    traceback.print_exc()
    screening_crew = None