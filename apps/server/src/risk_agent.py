import json
import os
from dotenv import load_dotenv
from typing import List, Dict, Any, Annotated
from pydantic import BaseModel, Field
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.callbacks import BaseCallbackHandler
from langgraph.graph import StateGraph, END
from typing_extensions import TypedDict
from operator import add
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
    """Callback to capture LLM tokens and stream them in real-time"""

    def __init__(self):
        self.buffer = ""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Capture each token and print it immediately"""
        self.buffer += token
        # Flush on punctuation or every 50 chars for better real-time feel
        if any(char in token for char in ['.', '!', '?', ',', ':', '\n']) or len(self.buffer) > 50:
            print(self.buffer, end="", flush=True)
            self.buffer = ""

    def on_llm_end(self, response, **kwargs) -> None:
        """Flush any remaining tokens"""
        if self.buffer:
            print(self.buffer, end="", flush=True)
            self.buffer = ""


def get_azure_llm():
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
            streaming=True,  # ✅ Enable streaming for real-time token output
            callbacks=[StreamingTokenCallback()]  # ✅ Stream tokens as they come
        )
    except Exception as e:
        print(f"❌ Failed to initialize Azure LLM: {str(e)}")
        raise e


# Initialize LLM
print("🔑 Authenticating with Azure KeyVault...")
llm = get_azure_llm()
print("✅ Azure OpenAI LLM Initialized")


def clean_numeric_value(value):
    """
    Clean numeric values that may have suffixes like 'x', '%', etc.
    Examples: '0.1938x' → 0.1938, '18.5%' → 18.5, '45.2' → 45.2
    """
    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return 0.0

    # Remove common suffixes: x, %, %, bps, etc.
    cleaned = value.strip().rstrip('xX%bpsBPS ').strip()

    # Try to convert to float
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def load_data(companies: List[Dict], mandate: Dict):
    """
    Load and validate companies and mandate data passed from frontend.

    Args:
        companies: List of company dictionaries
        mandate: Dictionary of mandate/risk parameters

    Returns:
        Tuple of (companies, mandate)
    """
    if not companies:
        raise ValueError("❌ Companies list cannot be empty")
    if not mandate:
        raise ValueError("❌ Mandate parameters cannot be empty")

    print(f"📊 {len(companies)} companies loaded from request")
    return companies, mandate


# === MODELS ===
class RiskScore(BaseModel):
    category: str
    score: str  # GREEN/YELLOW/RED
    reason: str  # "Mandate wants X, company has Y → COLOR"
    severity: float  # 0/5/10


class CompanyAnalysis(BaseModel):
    company_name: str
    overall_risk_score: float
    risk_scores: List[RiskScore]
    passes_mandate: bool
    recommendation: str


class AgentState(TypedDict):
    companies: List[Dict]
    mandate: Dict
    analyses: Annotated[List[CompanyAnalysis], add]
    filtered_companies: List[CompanyAnalysis]


# === LLM ===
# LLM instance is created per-request to enable streaming callbacks
# See get_azure_llm() function above


# === ROBUST JSON PARSER ===
class RobustJsonParser(JsonOutputParser):
    def parse_result(self, response):
        if hasattr(response, 'content'):
            text = response.content
        else:
            text = str(response)

        print(f"   📝 Raw: {text[:200]}...")

        # Clean tags
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<.*?>', '', text, flags=re.DOTALL)

        # Extract JSON
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{[^{}]*?(?:\{[^{}]*?\}[^{}]*?)*?\}', text)
            json_str = json_match.group(0) if json_match else text.strip()

        json_str = json_str.strip()
        json_str = re.sub(r'^json\s*:?\s*', '', json_str, flags=re.IGNORECASE)
        json_str = json_str.encode().decode('unicode_escape')

        print(f"   🔍 JSON: {json_str[:100]}...")

        try:
            json_data = json.loads(json_str)
            return self.pydantic_object(**json_data)
        except Exception as e:
            print(f"   ❌ Parse error: {e}")
            raise ValueError(f"JSON failed: {e}\nRaw: {json_str[:300]}")


# === LLM ANALYSIS WITH MANDATE COMPARISONS ===
def analyze_companies_llm(state: AgentState) -> AgentState:
    analyses = []
    parser = RobustJsonParser(pydantic_object=CompanyAnalysis)

    prompt = ChatPromptTemplate.from_template("""
    Score company vs FUND MANDATE. reason="Mandate wants X, company has Y → GREEN/YELLOW/RED"

    COMPANY: {company_name}
    FINANCIALS: Debt/Eq={debt_equity:.2f}, ROE={roe:.1f}%, P/E={pe:.1f}
    RISKS: {risks}
    MANDATE: {mandate_summary}

    reason EXACTLY: "Mandate wants [requirement], company has [actual] → COLOR (0/5/10)"

    Categories (6 exactly):
    1. Competitive Position
    2. Governance Quality  
    3. Customer Concentration Risk
    4. Vendor/Platform Dependency
    5. Regulatory/Legal Risk
    6. Business Model Complexity

    GREEN=0 (meets), YELLOW=5 (borderline), RED=10 (fails)
    passes_mandate=True if ≤1 RED risk
    overall_risk_score=average(severity)

    JSON only:
    {format_instructions}
    """)

    for i, company in enumerate(state["companies"]):
        company_name = company.get('Company ') or company.get('Company', f'Company_{i}')
        try:
            print(f"\n🔍 LLM → {company_name}")
            print(f"   ⏳ Loading company data...")

            # Clean numeric values that may have suffixes (e.g., '0.1938x' → 0.1938)
            debt_equity = clean_numeric_value(company.get('Debt / Equity', 0))
            roe = clean_numeric_value(company.get('Return on Equity', 0))
            pe = clean_numeric_value(company.get('P/E Ratio', 0))
            risks = company.get('Risks', {})

            print(f"   ⏳ Sending to LLM for analysis...")

            # Create fresh LLM instance with streaming callback for this company
            llm_streaming = get_azure_llm()
            raw_response = prompt | llm_streaming
            print("   🧠 LLM Thinking: ", end="", flush=True)

            response = raw_response.invoke({
                "company_name": company_name,
                "debt_equity": debt_equity, "roe": roe, "pe": pe,
                "risks": json.dumps(risks, indent=2),
                "mandate_summary": json.dumps(state["mandate"], indent=2),
                "format_instructions": parser.get_format_instructions()
            })

            print(f"\n   ⏳ Parsing LLM response...")
            analysis = parser.parse_result(response)

            # Show LLM comparisons
            print("   📊 MANDATE vs COMPANY:")
            for risk in analysis.risk_scores:
                print(f"   • {risk.category:<25} | {risk.reason}")
            print(f"   ✅ {analysis.overall_risk_score:.1f}/10 | Passes: {analysis.passes_mandate}")

            analyses.append(analysis)

        except Exception as e:
            print(f"⚠️ FAILED: {e}")
            fallback = CompanyAnalysis(
                company_name=company_name,
                overall_risk_score=5.0,
                risk_scores=[RiskScore(
                    category="LLMError", score="YELLOW",
                    reason=f"Analysis failed: {str(e)[:80]}", severity=5
                )],
                passes_mandate=False,
                recommendation="Manual review required"
            )
            analyses.append(fallback)

    return {"analyses": analyses}


def filter_safe(state: AgentState) -> AgentState:
    safer = [a for a in state["analyses"] if a.passes_mandate]
    print(f"\n✅ {len(safer)}/{len(state['companies'])} PASS MANDATE")
    return {"filtered_companies": safer}


def format_results(state: AgentState) -> AgentState:
    """Format and print results table"""
    filtered = state["filtered_companies"]
    total = len(state["companies"])

    print("\n" + "=" * 80)
    print("🏆 INVESTABLE COMPANIES (LLM w/ MANDATE COMPARISONS)")
    print("=" * 80)
    for i, c in enumerate(filtered, 1):
        print(f"{i:2d}. {c.company_name:<30} | {c.overall_risk_score:5.1f} | {c.recommendation}")

    passed = len(filtered)
    print(f"\n📊 {passed}/{total} ({100 * passed / total:.1f}%) PASS")

    return {}  # No state changes needed


# === GRAPH ===
workflow = StateGraph(AgentState)
workflow.add_node("analyze", analyze_companies_llm)
workflow.add_node("filter", filter_safe)
workflow.add_node("format", format_results)
workflow.set_entry_point("analyze")
workflow.add_edge("analyze", "filter")
workflow.add_edge("filter", "format")
workflow.add_edge("format", END)

app = workflow.compile()