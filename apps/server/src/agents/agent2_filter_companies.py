from langchain_classic.prompts import PromptTemplate
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

# from logging import setup_logging
from utils.tools import load_and_filter_companies  # Your fixed too

load_dotenv()
# setup_logging("filter_companies")

import sys
import atexit
from datetime import datetime
from pathlib import Path
# --- LOGGING SYSTEM (unchanged) ---
# log_dir = Path("ParsingSourcingAgent_Log")
# log_dir.mkdir(parents=True, exist_ok=True)
# timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
# log_path = log_dir / f"sourcing_run_{timestamp}.log"
# log_file = open(log_path, 'a', encoding='utf-8')

# class Tee:
#     def __init__(self, *streams):
#         self.streams = streams
#     def write(self, data):
#         for s in self.streams:
#             try: s.write(data)
#             except: pass
#     def flush(self):
#         for s in self.streams:
#             try: s.flush()
#             except: pass

# sys.stdout = Tee(sys.__stdout__, log_file)
# sys.stderr = Tee(sys.__stderr__, log_file)
# atexit.register(lambda: log_file.close())


# LLM = ChatGroq(model="qwen/qwen3-32b", temperature=0, api_key=os.getenv("GROQ_API_KEY"))

from utils.llm_testing import get_langchain_llm

LLM = get_langchain_llm()

if LLM is None:
    raise RuntimeError("LLM initialization failed: LLM is None")

# REACT_PROMPT = """Filter companies by USER filters ONLY → JSON output.
#
# TOOLS: {tools}
# USE TOOLS BY NAME: {tool_names}
#
# Format:
# Question: {input}
# Thought: [reasoning]
# Action: [{tool_names}]
# Action Input: [user_filters_json]
# Observation: [result]
# ...
# Thought: [final answer ready]
# Final Answer: [JSON]
#
# Question: {input}
# Thought: {agent_scratchpad}
# """

REACT_PROMPT = """  Filter companies by USER filters ONLY → JSON output.
Use this exact format for Thought:
Question: {input}
Thought: [Im a Sector & Industry Research Agent followed by "Your step-by-step research reasoning here"]
Action: [tool name from {tool_names}]
Action Input: [exact JSON input for tool]
Observation: [tool result]
...
Thought: [final analysis complete]
Final Answer: [Complete JSON output as returned by the tool]

Available tools: {tools}
Tool names: {tool_names}

Question: {input}
Thought: {agent_scratchpad}
"""


def create_sector_and_industry_research_agent():
#     prompt = PromptTemplate.from_template("""You are the Sector & Industry Research Agent within the Research and Idea Generation process of the Fund Mandate capability.
#
# You specialize in top-down analysis: identifying broader market trends, competitive landscapes, and macroeconomic tailwinds/headwinds affecting specific industries. Trigger for high-level thematic insights or comparative sector data to inform investment mandates.
#
# In EVERY Thought step, ALWAYS start with: "I'm a sector and industry research agent: [your top-down analysis reasoning here]".
#
# Return tool data as JSON without changes. Use `load_and_filter_companies` with user filters to get sector/industry data, then analyze for trends/landscapes.
#
# """+ REACT_PROMPT)
#     prompt = PromptTemplate.from_template("""You are a professional agent specialized in sector and industry research analysis for investment in fund mandate.
#
# Your role: In your thought add you're a Sector and Industry research agent and Return the response from the tool in the same format
# CONDITIONS:
# Return only the tool output in same format. Dont summarize or change anything.
# """ + REACT_PROMPT)
    prompt = PromptTemplate.from_template("""You are a professional agent specialized in sector and industry research analysis for investment in fund mandate.

Your role: In your thought add you're a Sector and Industry research agent and Return the response from the tool in the same format. If found 0 matches return the tool output
Use this exact format for Thought:
Question: {input}
Thought: [Im a Sector & Industry Research Agent followed by "Your step-by-step research reasoning here"]
Action: [tool name from {tool_names}]
Action Input: [exact JSON input for tool]
Observation: [tool result]
... (repeat Thought/Action/Observation)
Thought: [final analysis complete]
Final Answer: [Complete JSON output as returned by the tool]

Available tools: {tools}
Tool names: {tool_names}

Question: {input}
Thought: {agent_scratchpad}
""" )

    agent = create_react_agent(LLM, [load_and_filter_companies], prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=[load_and_filter_companies],
        verbose=False,
        handle_parsing_errors=True,
        return_intermediate_steps=True,  # ✅ Add this
        max_iterations=15
    )
    return executor

if __name__ == "__main__":
    agent = create_sector_and_industry_research_agent()
    user_input = '{"geography": "us", "sector": "technology", "industry": "software & IT services"}'
    result = agent.invoke({"input": user_input})
    print("FILTERED:", result["output"])