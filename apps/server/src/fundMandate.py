# from azure.ai.projects import AIProjectClient
# from azure.identity import DefaultAzureCredential
# from azure.ai.agents.models import ListSortOrder
# from fastapi import APIRouter, HTTPException
# from pydantic import BaseModel
#
#
# PROJECT_ENDPOINT = "https://fstoaihub1292141971.services.ai.azure.com/api/projects/fstoaihub1292141971-AgentsSample"
# AGENT_ID = "asst_Nm4bdHLpmI2W2VdwT2lF1Jr8"
#
#
# class QueryRequest(BaseModel):
#     content: str
#
#
# class QueryResponse(BaseModel):
#     response: str
#     status: str
#
#
# router = APIRouter()
#
#
# def get_project_client():
#     try:
#         client = AIProjectClient(
#             credential=DefaultAzureCredential(),
#             endpoint=PROJECT_ENDPOINT
#         )
#         return client
#     except Exception as e:
#         print(f"Failed to initialize Azure AI Project Client: {e}")
#         return None
#
#
# def query_agent(user_content: str) -> dict:
#     project = get_project_client()
#
#     if not project:
#         return {
#             "response": "Azure AI Project is not initialized",
#             "status": "error"
#         }
#
#     try:
#         thread = project.agents.threads.create()
#
#         project.agents.messages.create(
#             thread_id=thread.id,
#             role="user",
#             content=user_content
#         )
#
#         run = project.agents.runs.create_and_process(
#             thread_id=thread.id,
#             agent_id=AGENT_ID
#         )
#
#         if run.status == "failed":
#             return {
#                 "response": f"Agent run failed: {run.last_error}",
#                 "status": "error"
#             }
#
#         messages = project.agents.messages.list(
#             thread_id=thread.id,
#             order=ListSortOrder.ASCENDING
#         )
#
#         agent_response = None
#         for message in messages:
#             if message.role == "assistant" and message.text_messages:
#                 agent_response = message.text_messages[-1].text.value
#
#         if not agent_response:
#             return {
#                 "response": "No response from agent",
#                 "status": "error"
#             }
#
#         return {
#             "response": agent_response,
#             "status": "success"
#         }
#
#     except Exception as e:
#         return {
#             "response": f"Error processing query: {str(e)}",
#             "status": "error"
#         }
#
#
# @router.post("/chat", response_model=QueryResponse)
# async def chat(request: QueryRequest) -> QueryResponse:
#     """
#     Send a query to the Azure agent and get a response
#     """
#     result = query_agent(request.content)
#     return QueryResponse(
#         response=result["response"],
#         status=result["status"]
#     )



import json
import traceback
from typing import List, Dict, Any
from azure.ai.agents.models import ListSortOrder
from datetime import datetime
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Import CrewAI components from mandate_screening
try:
    from mandate_screening import screening_crew
except Exception as e:
    print(f"Error importing mandate_screening: {e}")
    screening_crew = None


PROJECT_ENDPOINT = "https://fstoaihub1292141971.services.ai.azure.com/api/projects/fstoaihub1292141971-AgentsSample"
AGENT_ID = "asst_Nm4bdHLpmI2W2VdwT2lF1Jr8"

class QueryRequest(BaseModel):
    content: str


class QueryResponse(BaseModel):
    response: str
    status: str


class ScreeningRequest(BaseModel):
    """Financial Screening Request Model"""
    mandate_parameters: dict
    companies: List[dict]

    class Config:
        json_schema_extra = {
            "example": {
                "mandate_parameters": {
                    "revenue": "> 40000000",
                    "debt_to_equity": "< 0.5",
                    "pe_ratio": "< 40"
                },
                "companies": [
                    {
                        "Company": "Microsoft",
                        "Sector": "Technology",
                        "Revenue": 281724.0,
                        "Debt / Equity": 0.3315,
                        "P/E Ratio": 34.47
                    }
                ]
            }
        }


class ScreeningResponse(BaseModel):
    """API Response Model - Wrapped Format"""
    company_details: List[Dict[str, Any]]


router = APIRouter()


def get_project_client():
    try:
        client = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint=PROJECT_ENDPOINT
        )
        return client
    except Exception as e:
        print(f"⚠️ Azure client not available: {e}")
        return None


def query_agent(user_content: str) -> dict:
        project = get_project_client()

        if not project:
            return {
                "response": "Azure AI Project is not initialized",
                "status": "error"
            }

        try:
            thread = project.agents.threads.create()

            project.agents.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_content
            )

            run = project.agents.runs.create_and_process(
                thread_id=thread.id,
                agent_id=AGENT_ID
            )

            if run.status == "failed":
                return {
                    "response": f"Agent run failed: {run.last_error}",
                    "status": "error"
                }

            messages = project.agents.messages.list(
                thread_id=thread.id,
                order=ListSortOrder.ASCENDING
            )

            agent_response = None
            for message in messages:
                if message.role == "assistant" and message.text_messages:
                    agent_response = message.text_messages[-1].text.value

            if not agent_response:
                return {
                    "response": "No response from agent",
                    "status": "error"
                }

            return {
                "response": agent_response,
                "status": "success"
            }

        except Exception as e:
            return {
                "response": f"Error processing query: {str(e)}",
                "status": "error"
            }

@router.post("/chat", response_model=QueryResponse)
async def chat(request: QueryRequest) -> QueryResponse:
    """
    Send a query to the Azure agent and get a response
    """
    result = query_agent(request.content)
    return QueryResponse(
        response=result["response"],
        status=result["status"]
    )
@router.post("/api/screen-companies", response_model=ScreeningResponse)
async def screen_companies_endpoint(request: ScreeningRequest):
    """
    Screen companies against mandate parameters using CrewAI Agent.

    Returns wrapped format: {"company_details": [...]}
    """
    try:
        # Validate inputs
        if not request.mandate_parameters:
            raise HTTPException(
                status_code=400,
                detail="mandate_parameters cannot be empty"
            )

        if not request.companies:
            raise HTTPException(
                status_code=400,
                detail="companies list cannot be empty"
            )

        # Check if crew is initialized
        if not screening_crew:
            raise HTTPException(
                status_code=500,
                detail="CrewAI screening crew not initialized"
            )

        print(f"\n{'=' * 80}")
        print(f"Screening Request Received")
        print(f"Mandate Parameters: {request.mandate_parameters}")
        print(f"Companies to Screen: {len(request.companies)}")
        print(f"{'=' * 80}\n")

        # Prepare inputs for crew
        inputs = {
            "mandate_parameters": request.mandate_parameters,
            "companies_list": request.companies
        }

        # Execute CrewAI
        result = screening_crew.kickoff(inputs=inputs)

        # print(f"\n{'─' * 80}")
        # print(f"Raw Crew Output Type: {type(result)}")
        # print(f"Raw Crew Output Preview: {str(result)[:500]}")
        # print(f"{'─' * 80}\n")
        parsed_result = {
            "company_details": []
        }

        result_text = str(result)

        try:
            # Extract JSON from crew output
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}') + 1

            if start_idx != -1 and end_idx > start_idx:
                json_str = result_text[start_idx:end_idx]
                raw_parsed = json.loads(json_str)

                print(f"Parsed JSON structure from crew output")

                if "company_details" in raw_parsed and isinstance(raw_parsed.get("company_details"), list):
                    # Already wrapped - use directly
                    parsed_result = raw_parsed
                    print(f"Detected wrapped format: {len(parsed_result['company_details'])} companies")
                else:
                    print("⚠️ Unexpected format structure")

            else:
                print("⚠️ No JSON found in crew output")

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parsing error: {e}")
        except Exception as e:
            print(f"⚠️ Parsing error: {e}")
            traceback.print_exc()

        print(f"\nScreening Complete! {len(parsed_result['company_details'])} companies found.\n")

        return parsed_result

    except HTTPException:
        raise
    except Exception as e:
        print(f"Screening Error: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Screening failed: {str(e)}"
        )
