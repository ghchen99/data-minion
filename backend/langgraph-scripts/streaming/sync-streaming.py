from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Initialize the Azure OpenAI chat model
# This returns a LangChain ChatModel wrapper
model = init_chat_model(
    "azure_openai:gpt-4.1",
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
)

class State(TypedDict):
    topic: str
    joke: str

def generate_joke(state: State):
    writer = get_stream_writer()

    # Custom progress signal
    writer({"status": "Starting LLM call"})

    # LLM tokens will stream automatically via `messages` mode
    response = model.invoke(
        [{"role": "user", "content": f"Tell me a joke about {state['topic']}"}]
    )

    writer({"status": "LLM finished"})

    return {"joke": response.content}

graph = (
    StateGraph(State)
    .add_node("generate_joke", generate_joke)
    .add_edge(START, "generate_joke")
    .add_edge("generate_joke", END)
    .compile()
)

for mode, chunk in graph.stream(
    {"topic": "cats"},
    stream_mode=["updates", "values", "messages", "custom"],
):
    print(mode, "→", chunk)

