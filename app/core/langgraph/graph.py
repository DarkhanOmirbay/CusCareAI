from typing import TypedDict
from langgraph.graph import StateGraph,START,END
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.core.logging import logger


llm = ChatOpenAI(model="gpt-4o",api_key=settings.OPENAI_API_KEY)

class AgentState(TypedDict):
    last_message:str
    response:str
    
    
    
async def process(state:AgentState)->AgentState:
    response = await llm.ainvoke(state["last_message"])
    logger.debug(f"\nAI: {response.content}")
    state["response"] = response.content
    return state
    
    
graph = StateGraph(AgentState)

graph.add_node("process",process)

graph.add_edge(START,"process")
graph.add_edge("process",END)

agent = graph.compile()


    
