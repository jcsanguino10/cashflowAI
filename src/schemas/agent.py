from typing import Annotated, Any, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    media: Optional[dict[str, Any]]
    media_output: Optional[str]
