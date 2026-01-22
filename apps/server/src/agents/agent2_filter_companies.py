from langchain_classic.prompts import PromptTemplate
from langchain_classic.agents import create_react_agent, AgentExecutor
from dotenv import load_dotenv
# from logging import setup_logging
from utils.tools import load_and_filter_companies  # Your fixed tool

load_dotenv()


from utils.llm_testing import get_langchain_llm

LLM = get_langchain_llm()

if LLM is None:
    raise RuntimeError("LLM initialization failed: LLM is None")

# ✅ FIXED PROMPT - DOUBLE BRACES EVERYWHERE
REACT_PROMPT = """Filter companies by USER filters ONLY → JSON output.

TOOLS: {tools}
USE TOOLS BY NAME: {tool_names}

Format:
Question: {input}
Thought: [reasoning]
Action: [{tool_names}]
Action Input: [user_filters_json]
Observation: [result]
...
Thought: [final answer ready]
Final Answer: [JSON]

Question: {input}
Thought: {agent_scratchpad}

RULES:
1. User gives exact filters: {{geography, sector, industry}}
2. Load companies_list.json
3. Match EXACTLY: company.Country==\"us\", company.Sector==\"technology\"
4. Case-insensitive matching
5. Handle null/empty values
6. RETURN JSON FROM TOOL - NO CHANGES"""


def create_filter_agent():
    prompt = PromptTemplate.from_template(REACT_PROMPT)
    # llm_with_tools = LLM.bind_tools(
    #     [load_and_filter_companies],
    #     stop=None
    # )
    agent = create_react_agent(LLM, [load_and_filter_companies], prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=[load_and_filter_companies],
        verbose=True,
        handle_parsing_errors=True,
        return_intermediate_steps=True,  # ✅ Add this
        max_iterations=3
    )
    return executor


if __name__ == "__main__":
    agent = create_filter_agent()
    user_input = '{"geography": "us", "sector": "technology", "industry": "software & IT services"}'
    result = agent.invoke({"input": user_input})
    print("FILTERED:", result["output"])