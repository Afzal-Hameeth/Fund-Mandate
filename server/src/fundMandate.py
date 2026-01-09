from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential
from azure.ai.agents.models import ListSortOrder


PROJECT_ENDPOINT = "https://fstoaihub1292141971.services.ai.azure.com/api/projects/fstoaihub1292141971-AgentsSample"
AGENT_ID = "asst_Nm4bdHLpmI2W2VdwT2lF1Jr8"


def get_project_client():

    try:
        client = AIProjectClient(
            credential=DefaultAzureCredential(),
            endpoint=PROJECT_ENDPOINT
        )
        return client
    except Exception as e:
        print(f"Failed to initialize Azure AI Project Client: {e}")
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