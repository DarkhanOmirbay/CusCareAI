from typing import TypedDict,Union
from langgraph.graph import StateGraph,START,END
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.core.logging import logger
from langchain_core.messages import BaseMessage
from openai import OpenAI,AsyncOpenAI



llm = ChatOpenAI(model="gpt-4o",api_key=settings.OPENAI_API_KEY)
client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


class AgentState(TypedDict):
    last_message:Union[str,BaseMessage]
    response:str
    system_message:Union[str,BaseMessage]
    tokens:int
    
    
    
async def process(state:AgentState)->AgentState:
    response = await llm.ainvoke([state["last_message"],state["system_message"]])
    logger.debug(f"\nAI: {response.content}")
    state["tokens"] = response.response_metadata["token_usage"]["total_tokens"]
    state["response"] = response.content
    return state
    
    
graph = StateGraph(AgentState)

graph.add_node("process",process)

graph.add_edge(START,"process")
graph.add_edge("process",END)

agent = graph.compile()


    
