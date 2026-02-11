"""
langgraph_data_agent_llm.py

LangGraph Data Agent fully LLM-driven.
"""

from typing import TypedDict, Optional, Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, RetryPolicy
from langgraph.checkpoint.memory import MemorySaver

from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage

import pandas as pd
import uuid
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

# =========================
# Load environment variables and init LLM
# =========================
load_dotenv()

model = init_chat_model(
    "azure_openai:gpt-4.1",
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
)

# =========================
# In-memory stores
# =========================
DATASETS: Dict[str, Dict] = {}
ARTIFACTS: Dict[str, Dict] = {}
DATAFRAME_STORE: Dict[str, pd.DataFrame] = {}

def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# =========================
# State Definition
# =========================
class DatasetAgentState(TypedDict):
    dataset_id: str
    prompt: Optional[str]
    thread_id: Optional[str]
    artifact_id: Optional[str]
    new_artifact_id: Optional[str]
    messages: Optional[List[str]]
    python_code: Optional[str]

# =========================
# Nodes
# =========================

def load_latest_dataset(state: DatasetAgentState) -> Dict:
    dataset_id = state["dataset_id"]
    latest_artifact_id = DATASETS[dataset_id]["artifacts"][-1]
    df = DATAFRAME_STORE[latest_artifact_id].copy()
    return {"artifact_id": latest_artifact_id, "df": df}


def llm_generate_python_code(state: DatasetAgentState) -> Dict:
    """
    LLM generates Python code to apply to the DataFrame.
    """
    prompt = state.get("prompt", "")
    df = DATAFRAME_STORE[state["artifact_id"]]

    llm_prompt = f"""
You are a Python pandas expert. 

You are given a DataFrame with columns: {list(df.columns)}.

Write Python code that modifies the DataFrame `df` to accomplish the following:

{prompt}

- Only modify `df`.
- Do not return anything.
- Use pandas.
- Do not print anything.
"""

    response = model.invoke(llm_prompt)

    return {"python_code": response.content}


def execute_python_code(state: DatasetAgentState) -> Dict:
    """
    Executes LLM-generated Python code.
    """
    df = DATAFRAME_STORE[state["artifact_id"]]
    code = state.get("python_code", "")
    local_ns = {"df": df, "pd": pd}

    try:
        exec(code, {}, local_ns)
    except Exception as e:
        return {"error": f"Failed to execute generated code: {e}"}

    new_df = local_ns.get("df")
    if not isinstance(new_df, pd.DataFrame):
        return {"error": "LLM code did not produce a valid DataFrame in variable 'df'."}

    return {"df": new_df}


def register_artifact(state: DatasetAgentState) -> Dict:
    """
    Register the new DataFrame as an artifact.
    """
    df = DATAFRAME_STORE[state["artifact_id"]]
    parent_id = state["artifact_id"]
    dataset_id = state["dataset_id"]
    thread_id = state.get("thread_id", "default_thread")

    artifact_id = generate_id("artifact")
    ARTIFACTS[artifact_id] = {
        "id": artifact_id,
        "dataset_id": dataset_id,
        "thread_id": thread_id,
        "type": "derived_dataset",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": [parent_id],
        "metadata": {"rows": len(df)},
    }

    DATAFRAME_STORE[artifact_id] = df
    DATASETS[dataset_id]["artifacts"].append(artifact_id)
    return {"new_artifact_id": artifact_id}


def summarize_artifact(state: DatasetAgentState) -> Dict:
    artifact_id = state.get("new_artifact_id")
    df = DATAFRAME_STORE.get(artifact_id)
    preview = df.head().to_dict(orient="records") if df is not None else []
    return {"messages": [f"Preview of artifact {artifact_id}: {preview}"]}


# =========================
# Graph Construction
# =========================
def build_dataset_agent_graph():
    workflow = StateGraph(DatasetAgentState)

    workflow.add_node("load_latest_dataset", load_latest_dataset)
    workflow.add_node("llm_generate_python_code", llm_generate_python_code)
    workflow.add_node("execute_python_code", execute_python_code)
    workflow.add_node("register_artifact", register_artifact)
    workflow.add_node("summarize_artifact", summarize_artifact)

    workflow.add_edge(START, "load_latest_dataset")
    workflow.add_edge("load_latest_dataset", "llm_generate_python_code")
    workflow.add_edge("llm_generate_python_code", "execute_python_code")
    workflow.add_edge("execute_python_code", "register_artifact")
    workflow.add_edge("register_artifact", "summarize_artifact")
    workflow.add_edge("summarize_artifact", END)

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# =========================
# Example Usage
# =========================
if __name__ == "__main__":
    # Example CSV setup
    dataset_id = generate_id("ds")
    df = pd.DataFrame({
        "name": ["Alice", "Bob", None],
        "sales": [100, 150, 200],
        "region": ["West", "East", "East"]
    })
    DATASETS[dataset_id] = {
        "id": dataset_id,
        "name": "Demo CSV",
        "original_file": "demo.csv",
        "schema": list(df.columns),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": "user_1",
        "artifacts": [],
    }
    base_artifact_id = generate_id("artifact")
    ARTIFACTS[base_artifact_id] = {
        "id": base_artifact_id,
        "dataset_id": dataset_id,
        "thread_id": None,
        "type": "base_dataset",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": [],
        "metadata": {"rows": len(df)},
    }
    DATAFRAME_STORE[base_artifact_id] = df
    DATASETS[dataset_id]["artifacts"].append(base_artifact_id)

    # Build agent
    agent = build_dataset_agent_graph()

    initial_state: DatasetAgentState = {
        "dataset_id": dataset_id,
        "prompt": "Remove rows with missing name and group total sales by region",
        "thread_id": "thread_123",
        "artifact_id": None,
        "new_artifact_id": None,
        "messages": [],
    }

    result = agent.invoke(
        initial_state,
        config={"configurable": {"thread_id": "thread_123"}}
    )
    print("Agent run complete:")
    print(result)
