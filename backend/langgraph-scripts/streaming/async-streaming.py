from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.config import get_stream_writer
from langchain.chat_models import init_chat_model
from dotenv import load_dotenv
import os

# Load environment variables from .env
load_dotenv()

# Initialize the Azure OpenAI chat model
# - Supports streaming
# - Emits token-level events when used with stream_mode="messages"
model = init_chat_model(
    "azure_openai:gpt-4o",
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
)

# -------------------------
# Graph state
# -------------------------
class State(TypedDict):
    topic: str
    joke: str

# -------------------------
# Async graph node
# -------------------------
async def generate_joke(state: State):
    # Stream writer lets this node emit arbitrary custom events
    # that are NOT part of the graph state (e.g. progress updates)
    writer = get_stream_writer()

    # ---- custom mode ----
    # Emitted immediately to signal progress (loading spinners, logs, etc.)
    writer({"status": "Starting LLM call"})

    # ---- messages mode ----
    # LLM tokens are streamed automatically while the model runs.
    # Each token is emitted as (message_chunk, metadata)
    response = await model.ainvoke(
        [{"role": "user", "content": f"Tell me a joke about {state['topic']}"}]
    )

    # ---- custom mode ----
    # Another custom progress signal after the LLM finishes
    writer({"status": "LLM finished"})

    # ---- updates / values modes ----
    # Returning state changes causes:
    # - updates: only this delta, tagged with node name
    # - values: the full graph state after this step
    return {"joke": response.content}

# -------------------------
# Graph definition
# -------------------------
graph = (
    StateGraph(State)
    .add_node("generate_joke", generate_joke)
    .add_edge(START, "generate_joke")
    .add_edge("generate_joke", END)
    .compile()
)

# -------------------------
# Async streaming execution
# -------------------------
async def main():
    async for mode, chunk in graph.astream(
        {"topic": "cats"},
        stream_mode=[
            # "updates":
            #   Streams ONLY the state changes returned by each node.
            #   Includes the node name.
            #   Best for progress tracking and observability.
            "updates",

            # "values":
            #   Streams the FULL graph state after each step.
            #   Best for simple UI state syncing.
            "values",

            # "messages":
            #   Streams LLM output token-by-token.
            #   Each event is (message_chunk, metadata).
            #   Best for ChatGPT-style typing UX.
            "messages",

            # "custom":
            #   Streams arbitrary user-defined data emitted via
            #   get_stream_writer() inside nodes or tools.
            #   Best for status messages, progress bars, tool output.
            "custom",
        ],
    ):
        print(mode, "→", chunk)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
