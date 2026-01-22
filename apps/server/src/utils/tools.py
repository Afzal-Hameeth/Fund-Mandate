import os
import json
import fitz
from pathlib import Path
from langchain_classic.tools import tool
from utils.llm import LLM

@tool
def scan_mandate_folder_and_parse() -> str:
    """Scan input_fund_mandate/ → Extract LATEST PDF text."""
    folder = Path(__file__).parent.parent / "input_fund_mandate"
    
    pdfs = list(folder.glob("*.pdf"))
    # print(f"🔍 Found PDFs: {[p.name for p in pdfs]}")
    
    if not pdfs:
        return f"❌ No PDF in {folder.absolute()}\nContents: {list(folder.iterdir()) if folder.exists() else 'Folder missing'}"

    latest = max(pdfs, key=os.path.getmtime)
    doc = fitz.open(latest)
    text = "".join(page.get_text() for page in doc)
    doc.close()
    return f"PDF: {latest.name}\nTEXT ({len(text)} chars):\n{text[:4000]}"


# @tool
# def extract_criteria(raw_text: str, user_params: str = "{}") -> str:
#     """Parse text → Extract criteria → JSON format."""
#     prompt = f"""From text extract criteria. User params: {user_params}

# {raw_text}

# JSON ONLY:
# {{
#   "mandate": {{
#     "fund" : "[fund_name/size]",
#     "geography": "[regions]",
#     "sector": "[industries]",
#     "revenue": "[thresholds]",
#     "ebitda": "[thresholds]",
#     "growth": "[thresholds]",
#     "exclude": "[sectors]"
#   }},
#   "user_selected": {user_params}
# }}"""
#     result = LLM.invoke(prompt).content.strip()
#     return result

@tool
def extract_criteria(raw_text: str, user_params: str = "{}") -> str:
    """Parse text → Extract criteria → JSON format."""
    prompt = f"""From the fund mandate text below, extract ONLY these exact fields into JSON.
Ignore anything else. Leave empty string "" if not found.
ALWAYS use this exact structure - no extra fields!

{raw_text}

JSON ONLY - exact template:
{{
  "mandate": {{
    "fund_name": "[fund name- e.g. 'ABC Fund']",
    "fund_size": "[fund size - e.g. '500 million USD']",
    "sourcing_parameters": {{
      "country": "",
      "sector": "",
      "industry": ""
    }},
    "screening_parameters": {{
      "revenue": "",
      "ebitda": "",
      "growth": "",
      "gross_profit_margin": "",
      "net_income": "",
      "return_on_equity": "",
      "debt_to_equity": "",
      "pe_ratio": "",
      "price_to_book": "",
      "market_cap": "",
      "dividend_yield": ""
    }},
    "risk_parameters": {{
      "competitive_position": "",
      "governance_quality": "",
      "customer_concentration_risk": "",
      "vendor_platform_dependency": "",
      "regulatory_legal_risk": "",
      "business_model_complexity": ""
    }}
  }}
}}"""
    result = LLM.invoke(prompt).content.strip()
    return result

@tool
def load_and_filter_companies(user_filters_json: str) -> str:
    """Load data/companies_list.json → Filter by user filters → JSON."""
    try:
        # 📁 Find data folder relative to THIS file (src/main.py)
        data_dir = Path(__file__).parent.parent / "../data"
        companies_file = data_dir / "companies_list.json"
        
        # Verify file exists
        if not companies_file.exists():
            return f"❌ File not found: {companies_file.absolute()}"
        
        filters = json.loads(user_filters_json)
        print(f"🔍 Filtering: {filters}")

        # Handle nested input {'additionalProp1': {...}}
        if 'additionalProp1' in filters:
            filters = filters['additionalProp1']

        with open(companies_file) as f:
            companies = json.load(f)

        filtered = []
        for company in companies:
            match = True
            for key, user_value in filters.items():
                company_value = company.get(key, "")
                if company_value and str(company_value).lower() != str(user_value).lower():
                    match = False
                    break
            if match:
                filtered.append(company)

        return json.dumps({
            "total_companies": len(companies),
            "qualified": filtered[:50],
            "filters_applied": filters,
            "match_count": len(filtered),  # Total matches found
            "qualified_count": len(filtered[:50]),
            "data_file": str(companies_file.absolute())
        }, indent=2)
        
    except Exception as e:
        return f"Error: {str(e)}"