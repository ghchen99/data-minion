"""
email_agent_langgraph.py

A complete, self-contained example of a customer support email agent
implemented using LangGraph.

This file demonstrates:
- Workflow decomposition into graph nodes
- Explicit state design
- LLM-based routing with Command objects
- Human-in-the-loop using interrupt()
- Error handling and retry policies
- Durable execution with checkpointing

This is a reference implementation meant for learning and extension,
not a production-ready system.
"""

# =========================
# Imports
# =========================

from typing import TypedDict, Literal, List, Dict, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt, RetryPolicy
from langgraph.checkpoint.memory import MemorySaver

from langchain.messages import HumanMessage

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


# =========================
# State Definition
# =========================

"""
The state is the shared memory for the entire graph.

Design principles:
- Store raw data only
- Avoid formatted prompts or derived strings
- Include only what must persist across steps
"""


class EmailClassification(TypedDict):
    intent: Literal["question", "bug", "billing", "feature", "complex"]
    urgency: Literal["low", "medium", "high", "critical"]
    topic: str
    summary: str


class EmailAgentState(TypedDict):
    # Raw email inputs (cannot be reconstructed later)
    email_content: str
    sender_email: str
    email_id: str

    # Outputs of reasoning steps
    classification: Optional[EmailClassification]

    # External data fetches (expensive or non-deterministic)
    search_results: Optional[List[str]]
    customer_history: Optional[Dict]

    # Generated content
    draft_response: Optional[str]

    # Debug / trace messages (optional but helpful)
    messages: Optional[List[str]]


# =========================
# Node Implementations
# =========================

def read_email(state: EmailAgentState) -> Dict:
    """
    Read and parse the incoming email.

    Design notes:
    - This node does NOT decide anything
    - It simply prepares the system for downstream reasoning
    - In real systems, this might normalize HTML, strip signatures, etc.
    """
    return {
        "messages": [
            HumanMessage(
                content=f"Processing email from {state['sender_email']}"
            )
        ]
    }


def classify_intent(
    state: EmailAgentState
) -> Command[
    Literal[
        "search_documentation",
        "bug_tracking",
        "human_review",
        "draft_response",
    ]
]:
    """
    Classify the email using an LLM and decide the next step.

    Why this node controls routing:
    - Classification is inherently probabilistic
    - LLMs are good at nuanced decisions
    - Centralizing routing logic makes behavior easier to audit
    """

    structured_llm = model.with_structured_output(EmailClassification)

    prompt = f"""
    Analyze the following customer email.

    Email content:
    {state['email_content']}

    From:
    {state['sender_email']}

    Classify the email by:
    - intent
    - urgency
    - topic
    - short summary
    """

    classification = structured_llm.invoke(prompt)

    # Routing rules (business logic)
    if classification["intent"] == "billing" or classification["urgency"] == "critical":
        goto = "human_review"
    elif classification["intent"] in ["question", "feature"]:
        goto = "search_documentation"
    elif classification["intent"] == "bug":
        goto = "bug_tracking"
    else:
        goto = "draft_response"

    return Command(
        update={"classification": classification},
        goto=goto,
    )


def search_documentation(
    state: EmailAgentState,
) -> Command[Literal["draft_response"]]:
    """
    Retrieve relevant documentation from a knowledge base.

    Design notes:
    - Returns raw document chunks, not summaries
    - LLM later decides how to use them
    - Retry policy handles transient API issues
    """

    classification = state.get("classification") or {}
    query = f"{classification.get('intent', '')} {classification.get('topic', '')}"

    # Placeholder for real search integration
    # In production: vector DB, keyword search, hybrid retrieval, etc.
    search_results = [
        "Reset your password via Settings > Security > Change Password",
        "Passwords must be at least 12 characters long",
        "Use uppercase, lowercase, numbers, and symbols",
    ]

    return Command(
        update={"search_results": search_results},
        goto="draft_response",
    )


def bug_tracking(
    state: EmailAgentState,
) -> Command[Literal["draft_response"]]:
    """
    Create or update a bug tracking ticket.

    Design notes:
    - Bug creation happens regardless of response drafting
    - Ticket ID is returned so it can be referenced in the reply
    - This node is an *action step*
    """

    # Placeholder for bug tracker API call
    ticket_id = "BUG-12345"

    return Command(
        update={
            "search_results": [f"Bug ticket {ticket_id} created and linked"],
        },
        goto="draft_response",
    )


def draft_response(
    state: EmailAgentState,
) -> Command[Literal["human_review", "send_reply"]]:
    """
    Draft a customer-facing response.

    Design notes:F
    - Formats prompts on-demand from raw state
    - Does not send anything directly
    - Decides whether human review is required
    """

    classification = state.get("classification") or {}

    context_blocks = []

    if state.get("search_results"):
        docs = "\n".join(f"- {doc}" for doc in state["search_results"])
        context_blocks.append(f"Relevant information:\n{docs}")

    if state.get("customer_history"):
        context_blocks.append(
            f"Customer tier: {state['customer_history'].get('tier', 'standard')}"
        )

    prompt = f"""
    Draft a professional and helpful response to this customer email:

    Email:
    {state['email_content']}

    Intent: {classification.get('intent')}
    Urgency: {classification.get('urgency')}

    {chr(10).join(context_blocks)}

    Guidelines:
    - Be clear and empathetic
    - Address the user's issue directly
    - Do not mention internal systems unless necessary
    """

    response = model.invoke(prompt)

    needs_human_review = (
        classification.get("urgency") in ["high", "critical"]
        or classification.get("intent") == "complex"
    )

    return Command(
        update={"draft_response": response.content},
        goto="human_review" if needs_human_review else "send_reply",
    )


def human_review(
    state: EmailAgentState,
) -> Command[Literal["send_reply", END]]:
    """
    Pause execution and request human input.

    Critical LangGraph rule:
    - interrupt() MUST be the first call in this function
    - Any code before it will re-run on resume
    """

    decision = interrupt(
        {
            "email_id": state["email_id"],
            "original_email": state["email_content"],
            "draft_response": state.get("draft_response"),
            "classification": state.get("classification"),
            "instructions": "Approve, edit, or reject this response",
        }
    )

    if decision.get("approved"):
        return Command(
            update={
                "draft_response": decision.get(
                    "edited_response", state.get("draft_response")
                )
            },
            goto="send_reply",
        )

    # Rejected → human handles manually
    return Command(update={}, goto=END)


def send_reply(state: EmailAgentState) -> Dict:
    """
    Send the email response.

    Design notes:
    - No retry logic here for unexpected failures
    - Let infrastructure errors surface for visibility
    - This is a terminal side-effect
    """

    print(f"Sending reply for email {state['email_id']}:")
    print(state["draft_response"])
    print("-" * 40)

    return {}


# =========================
# Graph Construction
# =========================

def build_graph():
    """
    Wire all nodes together into a LangGraph StateGraph.

    Notice:
    - Very few explicit edges
    - Most routing happens via Command.goto
    """

    workflow = StateGraph(EmailAgentState)

    workflow.add_node("read_email", read_email)
    workflow.add_node("classify_intent", classify_intent)

    workflow.add_node(
        "search_documentation",
        search_documentation,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    workflow.add_node("bug_tracking", bug_tracking)
    workflow.add_node("draft_response", draft_response)
    workflow.add_node("human_review", human_review)
    workflow.add_node("send_reply", send_reply)

    # Essential edges only
    workflow.add_edge(START, "read_email")
    workflow.add_edge("read_email", "classify_intent")
    workflow.add_edge("send_reply", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# =========================
# Example Execution
# =========================

if __name__ == "__main__":
    """
    Example run demonstrating:
    - Initial invocation
    - Human-in-the-loop pause
    - Resume with approval
    """

    app = build_graph()

    initial_state: EmailAgentState = {
        "email_content": "I was charged twice for my subscription! This is urgent!",
        "sender_email": "customer@example.com",
        "email_id": "email_123",
        "classification": None,
        "search_results": None,
        "customer_history": None,
        "draft_response": None,
        "messages": [],
    }

    config = {"configurable": {"thread_id": "customer_123"}}

    # First run — will pause at human_review
    result = app.invoke(initial_state, config)
    print("Execution paused for human review:")
    print(result["__interrupt__"])

    # Resume with human approval
    resume_command = Command(
        resume={
            "approved": True,
            "edited_response": (
                "We’re very sorry for the duplicate charge. "
                "I’ve initiated an immediate refund, and you should "
                "see it reflected within 3–5 business days."
            ),
        }
    )

    app.invoke(resume_command, config)
