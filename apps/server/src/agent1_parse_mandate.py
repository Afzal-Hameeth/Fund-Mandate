from langchain_classic.prompts import PromptTemplate
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv

# from logging import setup_logging
from tools import scan_mandate_folder_and_parse, extract_criteria

load_dotenv()
# setup_logging("parse_mandate")

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

from llm_testing import get_langchain_llm

LLM = get_langchain_llm()

if LLM is None:
    raise RuntimeError("LLM initialization failed: LLM is None")

REACT_PROMPT = """Parse mandate → Extract criteria → JSON output.

TOOLS: {tools}
USE TOOLS BY NAME: {tool_names}

Format:
Question: {input}
Thought: [reasoning]
Action: [{tool_names}]
Action Input: [input]
Observation: [result]
...
Thought: [final answer ready]
Final Answer: [JSON]

WORKFLOW:
1. scan_mandate_folder_and_parse → get PDF text
2. extract_criteria → get JSON (your FINAL OUTPUT)

CRITICAL RULES:
- Use the tools properly.
- Return the result of extract_criteria as FINAL ANSWER.
- DO NOT rephrase, summarize, or modify the JSON produced by extract_criteria tool
- Final JSON structure is ALWAYS identical with fund_name, fund_size, sourcing parameters , screening parameters and risk parameters

Question: {input}
Thought: {agent_scratchpad}"""


def create_parse_agent():
    prompt = PromptTemplate.from_template(REACT_PROMPT)
    agent = create_react_agent(LLM, [scan_mandate_folder_and_parse, extract_criteria], prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=[scan_mandate_folder_and_parse, extract_criteria],
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5
    )
    return executor


if __name__ == "__main__":
    agent = create_parse_agent()
    result = agent.invoke({"input": "Scan input_fund_mandate and extract criteria"})
    print("MANDATE JSON:", result["output"])