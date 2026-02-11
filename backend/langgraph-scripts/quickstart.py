# =========================
# Step 1: Define tools and model
# =========================

from langchain.tools import tool
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

# -------------------------
# Define tools
# -------------------------
# Each @tool-decorated function becomes:
# - JSON-schema describable
# - Callable by the LLM via tool calls

@tool
def multiply(a: int, b: int) -> int:
    """Multiply `a` and `b`."""
    return a * b


@tool
def add(a: int, b: int) -> int:
    """Adds `a` and `b`."""
    return a + b


@tool
def divide(a: int, b: int) -> float:
    """Divide `a` and `b`."""
    return a / b


# Collect tools in a list (used for binding)
tools = [add, multiply, divide]

# Map tool name -> actual Python function
# Used later when executing tool calls
tools_by_name = {tool.name: tool for tool in tools}

# Bind tools to the model
# This enables the LLM to emit structured tool_calls
model_with_tools = model.bind_tools(tools)

# =========================
# Step 2: Define state
# =========================

from langchain.messages import AnyMessage
from typing_extensions import TypedDict, Annotated
import operator

class MessagesState(TypedDict):
    # Accumulated conversation history:
    # HumanMessage, AIMessage, ToolMessage, etc.
    #
    # Annotated[..., operator.add] tells LangGraph:
    # "When a node returns new messages, APPEND them"
    messages: Annotated[list[AnyMessage], operator.add]

    # Counter tracking how many times the LLM was called
    llm_calls: int

# =========================
# Step 3: Define model node
# =========================

from langchain.messages import SystemMessage

def llm_call(state: dict):
    """
    Calls the LLM with the current conversation state.

    Input:
      state = {
        "messages": [...],
        "llm_calls": int
      }

    Output:
      Partial state update:
      {
        "messages": [AIMessage(...)],
        "llm_calls": incremented
      }
    """

    # Build the prompt sent to the LLM:
    # - System instructions
    # - Full message history so far
    response = model_with_tools.invoke(
        [
            SystemMessage(
                content="You are a helpful assistant tasked with performing arithmetic on a set of inputs."
            )
        ]
        + state["messages"]
    )

    return {
        # Wrap response in a list so LangGraph can append it
        "messages": [response],

        # Increment the LLM call counter
        "llm_calls": state.get("llm_calls", 0) + 1
    }

# =========================
# Step 4: Define tool node
# =========================

from langchain.messages import ToolMessage

def tool_node(state: dict):
    """
    Executes any tool calls requested by the LLM.

    Expects the *last* message to be an AIMessage
    containing one or more tool_calls.
    """

    result = []

    # Iterate over all tool calls requested by the LLM
    for tool_call in state["messages"][-1].tool_calls:
        # Look up the actual Python function
        tool = tools_by_name[tool_call["name"]]

        # Execute the tool with the provided arguments
        observation = tool.invoke(tool_call["args"])

        # Wrap the result in a ToolMessage
        # tool_call_id links result back to the request
        result.append(
            ToolMessage(
                content=observation,
                tool_call_id=tool_call["id"]
            )
        )

    # Return new messages to be appended to state
    return {"messages": result}

# =========================
# Step 5: Define routing logic
# =========================

from typing import Literal
from langgraph.graph import StateGraph, START, END

def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    """
    Decides whether the agent should:
    - Call a tool
    - Or stop execution

    This function DOES NOT modify state.
    """

    messages = state["messages"]
    last_message = messages[-1]

    # If the LLM requested tool calls,
    # route execution to the tool node
    if last_message.tool_calls:
        return "tool_node"

    # Otherwise, the LLM produced a final answer
    return END

# =========================
# Step 6: Build the agent
# =========================

# Create a graph with MessagesState as shared state
agent_builder = StateGraph(MessagesState)

# Register nodes
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", tool_node)

# Wire execution flow:
# START → LLM
agent_builder.add_edge(START, "llm_call")

# After LLM:
# - If tool requested → tool_node
# - Else → END
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    ["tool_node", END]
)

# After tool execution, go back to the LLM
agent_builder.add_edge("tool_node", "llm_call")

# Compile the graph into a runnable agent
agent = agent_builder.compile()

# =========================
# Invoke the agent
# =========================

from langchain.messages import HumanMessage

# Initial user message
messages = [HumanMessage(content="Add 3 and 4.")]

# Run the agent
messages = agent.invoke({"messages": messages})

# Pretty-print the full message history
for m in messages["messages"]:
    m.pretty_print()
