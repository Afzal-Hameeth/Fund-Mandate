import os
import json
import re
from typing import Optional, List
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# LLM Configuration (Gemini)
# ============================================================================

groq_api_key = os.getenv("GROQ_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")

if not groq_api_key:
    raise ValueError("GROQ_API_KEY not found in .env file!")

print(f" GROQ API Key loaded: {groq_api_key[:20]}...")

try:
    # Use GROQ with CrewAI LLM
    llm = LLM(
        model="groq/meta-llama/llama-4-scout-17b-16e-instruct",
              # "llama-3.3-70b-versatile",  # Fast, reliable GROQ model
        api_key=groq_api_key,
        temperature=0.3,
        max_tokens=2048
    )
    print("GROQ LLM initialized successfully with mixtral-8x7b-32768")
except Exception as e:
    print(f"LLM initialization error: {e}")
    llm = None

#
# try:
#     llm = LLM(
#         model="google_ai/gemini-2.0-flash" ,
#         api_key=os.getenv("GOOGLE_API_KEY"),
#         temperature=0.3
#     )
#     print("✅ LLM initialized successfully")
# except Exception as e:
#     print(f"❌ LLM initialization error: {e}")
#     llm = None


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

                for param_name, constraint_str in mandate_parameters.items():
                    operator, threshold = parse_constraint(constraint_str)
                    company_value = get_company_value(company, param_name)

                    if company_value is None:
                        all_passed = False
                        break

                    if not compare_values(company_value, operator, threshold):
                        all_passed = False
                        break

                if all_passed:
                    passed_companies.append({
                        "company_name": company_name,
                        "sector": sector,
                        "status": "PASS",
                        "reason": f"{company_name} meets all mandate criteria. Strong financial metrics aligned with fund objectives.",
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
# ...existing code...

class FinancialScreeningTool(BaseTool):
    """
    Validates companies against mandate parameters.
    Takes mandate parameters and company list, returns only PASSED companies.
    """
    name: str = "financial_screening_tool"
    description: str = """Screen companies against mandate parameters and return only those that pass ALL criteria."""

    def _run(self, mandate_parameters: dict, companies: list) -> str:
        """
        Screen companies and return only passed ones

        Args:
            mandate_parameters: dict with screening criteria
            companies: list of company dicts to screen

        Returns:
            JSON string with passed companies in wrapped format
        """
        try:
            print(f"\n Tool Screening {len(companies)} companies against {len(mandate_parameters)} criteria...")

            if not mandate_parameters or not companies:
                print("Empty mandate or companies list")
                return json.dumps({"company_details": []})

            passed_companies = screen_companies_simple(mandate_parameters, companies)
            print(f"Tool Result: {len(passed_companies)} companies passed")

            company_details_list = []
            for company in passed_companies:
                company_data = company["company_details"].copy()  # Get full company object
                company_data["status"] = "Pass"
                company_data["reason"]=""
                # company_data["reason"] = company.get("reason", "")
                company_details_list.append(company_data)

            formatted_response = {
                "company_details": company_details_list
            }

            print(f"Tool Output: {json.dumps(formatted_response, default=str)[:300]}...")
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
    financial_screening_agent = Agent(
        role="Financial Screening Specialist",
        goal="""Evaluate companies against fund mandate parameters.
        Use financial_screening_tool to validate each company.
        Return ONLY valid JSON output with screening results.""",
        backstory="""You are an expert financial analyst specializing in investment screening.
        You have deep knowledge of financial metrics, valuation multiples, and 
        institutional investment criteria. You evaluate companies objectively
        against predefined mandate parameters.""",
        llm=llm,
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

        OUTPUT FORMAT (STRICT JSON):
        {
            "company_details": [
                {
                    "Company": "company_name",
                    "Country": "country",
                    "Sector": "sector",
                    "status": "Pass",
                    "reason": "reason it has passed",
                    ... all financial metrics
                }
            ]
        }
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
                    ... all financial metrics
                }
            ]
        }",
                    ... all financial metrics
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