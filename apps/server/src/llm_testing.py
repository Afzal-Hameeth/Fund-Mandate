import os
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI


def get_langchain_llm():
    """
    Returns ready-to-use AzureChatOpenAI instance from Key Vault
    """

    # 1. Key Vault Configuration
    key_vault_name = "fstodevzaureopenai"
    key_vault_url = f"https://fstodevazureopenai.vault.azure.net/"

    # 2. Authenticate and Initialize Secret Client
    credential = DefaultAzureCredential()
    kv_client = SecretClient(vault_url=key_vault_url, credential=credential)

    try:
        # 3. Retrieve secrets from Key Vault
        subscription_key = kv_client.get_secret("llm-api-key").value
        endpoint = kv_client.get_secret("llm-base-endpoint").value
        deployment = kv_client.get_secret("llm-41").value
        api_version = kv_client.get_secret("llm-41-version").value

        print(f" Config loaded: {deployment} @ {endpoint[:40]}...")

    except Exception as e:
        print(f" Key Vault error: {e}")
        raise

    # 4. ✅ LANGCHAIN AzureChatOpenAI (supports .invoke() + agents)
    LLM = AzureChatOpenAI(
        azure_deployment=deployment,
        openai_api_version=api_version,
        azure_endpoint=endpoint,
        api_key=subscription_key,
        temperature=0
    )

    return LLM


# For direct testing
if __name__ == "__main__":
    LLM = get_langchain_llm()
    print("✅ LLM exported and ready!")