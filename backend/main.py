"""
langgraph_data_agent_llm_stream.py

LangGraph Data Agent fully LLM-driven with streaming support, storing artifacts and code locally.
"""

from typing import TypedDict, Optional, Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage

import pandas as pd
import uuid
from datetime import datetime, timezone
import os
import json
from dotenv import load_dotenv

# =========================
# Config
# =========================
BASE_STORAGE_DIR = "data_agent_storage"
DATASET_DIR = os.path.join(BASE_STORAGE_DIR, "datasets")
ARTIFACT_DIR = os.path.join(BASE_STORAGE_DIR, "artifacts")
CODE_DIR = os.path.join(BASE_STORAGE_DIR, "python_code")

for d in [DATASET_DIR, ARTIFACT_DIR, CODE_DIR]:
    os.makedirs(d, exist_ok=True)

# =========================
# Load environment variables and init LLM
# =========================
load_dotenv()

model = init_chat_model(
    "azure_openai:gpt-4.1",
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
)

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
    python_code_file: Optional[str]

# =========================
# Helpers
# =========================
def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

def save_json(obj: dict, path: str):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)

def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)

def save_dataframe(df: pd.DataFrame, artifact_id: str) -> str:
    path = os.path.join(ARTIFACT_DIR, f"{artifact_id}.csv")
    df.to_csv(path, index=False)
    return path

def load_dataframe(artifact_id: str) -> pd.DataFrame:
    path = os.path.join(ARTIFACT_DIR, f"{artifact_id}.csv")
    return pd.read_csv(path)

def save_python_code(code: str, artifact_id: str) -> str:
    path = os.path.join(CODE_DIR, f"{artifact_id}.py")
    with open(path, "w") as f:
        f.write(code)
    return path

# =========================
# Nodes (async streaming)
# =========================
async def load_latest_dataset(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    writer({"status": "Loading latest dataset artifact..."})

    dataset_id = state["dataset_id"]
    dataset_meta_path = os.path.join(DATASET_DIR, f"{dataset_id}.json")
    dataset_meta = load_json(dataset_meta_path)
    latest_artifact_id = dataset_meta["artifacts"][-1]

    df = load_dataframe(latest_artifact_id)

    writer({"status": f"Loaded artifact {latest_artifact_id}"})
    return {"artifact_id": latest_artifact_id, "df": df}

async def llm_generate_python_code(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    prompt = state.get("prompt", "")
    df = load_dataframe(state["artifact_id"])

    llm_prompt = f"""
You are a Python pandas expert. 

You are given a DataFrame with schema: {df.info()}.

Write Python code that modifies the DataFrame `df` to accomplish the following:

{prompt}

- Only modify `df`.
- Do not return anything.
- Use pandas.
- Do not print anything.
- Do NOT include any markdown backticks in your output.
"""

    writer({"status": "LLM call started for python code generation..."})
    response = await model.ainvoke([{"role": "user", "content": llm_prompt}])
    writer({"status": "LLM call finished"})

    code = response.content.strip()
    if code.startswith("```") and code.endswith("```"):
        lines = code.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines[-1].startswith("```"):
            lines = lines[:-1]
        code = "\n".join(lines)

    # Save code to file
    code_file = save_python_code(code, state["artifact_id"])

    return {"python_code_file": code_file}

async def execute_python_code(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    df = load_dataframe(state["artifact_id"])
    code_file = state.get("python_code_file", "")

    writer({"status": f"Executing Python code from {code_file}..."})

    local_ns = {"df": df, "pd": pd}
    try:
        with open(code_file) as f:
            code = f.read()
        exec(code, {}, local_ns)
    except Exception as e:
        writer({"status": f"Error executing code: {e}"})
        return {"error": f"Failed to execute generated code: {e}"}

    new_df = local_ns.get("df")
    if not isinstance(new_df, pd.DataFrame):
        error_msg = "Python code did not produce a valid DataFrame in variable 'df'."
        writer({"status": error_msg})
        return {"error": error_msg}

    # Overwrite CSV for next step
    save_dataframe(new_df, state["artifact_id"])
    writer({"status": "Code executed successfully"})
    return {"df": new_df}

async def register_artifact(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    df = load_dataframe(state["artifact_id"])
    parent_id = state["artifact_id"]
    dataset_id = state["dataset_id"]
    thread_id = state.get("thread_id", "default_thread")

    new_artifact_id = generate_id("artifact")
    artifact_meta = {
        "id": new_artifact_id,
        "dataset_id": dataset_id,
        "thread_id": thread_id,
        "type": "derived_dataset",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": [parent_id],
        "metadata": {"rows": len(df)},
    }

    # Save artifact CSV
    save_dataframe(df, new_artifact_id)

    # Save metadata
    save_json(artifact_meta, os.path.join(ARTIFACT_DIR, f"{new_artifact_id}.json"))

    # Update dataset metadata
    dataset_meta_path = os.path.join(DATASET_DIR, f"{dataset_id}.json")
    dataset_meta = load_json(dataset_meta_path)
    dataset_meta["artifacts"].append(new_artifact_id)
    save_json(dataset_meta, dataset_meta_path)

    writer({"status": f"Registered new artifact {new_artifact_id}"})
    return {"new_artifact_id": new_artifact_id}

async def summarize_artifact(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    artifact_id = state.get("new_artifact_id")
    df = load_dataframe(artifact_id)
    preview = df.head().to_dict(orient="records")

    writer({"status": f"Preview of artifact {artifact_id} generated"})
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
async def main():
    # Example CSV setup
    dataset_id = generate_id("ds")
    import pandas as pd

    df = pd.DataFrame({
        "name": ["Alice", "Bob", None, "Diana", "Eve", "Frank", None,
                "George", "Hannah", "Ian", "Jane", "Kyle", "Laura", "Mike", "Nina", "Oscar", None, "Paula", "Quinn", "Rita"],
        "sales": [100, 150, 200, None, 50, 300, 120,
                220, 180, None, 90, 130, 160, 210, None, 140, 170, 200, None, 190],
        "region": ["West", "East", "East", "West", "North", "East", "South",
                "North", "South", "West", "East", "North", "West", "East", "South", "North", "West", "South", "East", "North"],
        "product": ["A", "B", "A", "C", "B", "A", "C",
                    "B", "C", "A", "B", "C", "A", "B", "C", "A", "B", "C", "A", "B"],
        "date": ["2026-01-01", "2026-01-02", "2026-01-02", "2026-01-03", None, "2026-01-01", "2026-01-03",
                "2026-01-04", "2026-01-05", "2026-01-05", "2026-01-06", "2026-01-07", None, "2026-01-08", "2026-01-08", "2026-01-09", "2026-01-10", "2026-01-10", None, "2026-01-11"]
    })
    # Save original CSV
    original_file_path = os.path.join(DATASET_DIR, f"{dataset_id}_original.csv")
    df.to_csv(original_file_path, index=False)

    dataset_meta = {
        "id": dataset_id,
        "name": "Demo CSV",
        "original_file": original_file_path,  # store path to original CSV
        "schema": list(df.columns),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": "user_1",
        "artifacts": [],
    }

    dataset_meta_path = os.path.join(DATASET_DIR, f"{dataset_id}.json")
    save_json(dataset_meta, dataset_meta_path)

    # Save base artifact (copy of original dataset)
    base_artifact_id = generate_id("artifact")
    save_dataframe(df, base_artifact_id)
    artifact_meta = {
        "id": base_artifact_id,
        "dataset_id": dataset_id,
        "thread_id": None,
        "type": "base_dataset",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": [],
        "metadata": {"rows": len(df)},
    }
    save_json(artifact_meta, os.path.join(ARTIFACT_DIR, f"{base_artifact_id}.json"))

    # Update dataset metadata
    dataset_meta["artifacts"].append(base_artifact_id)
    save_json(dataset_meta, dataset_meta_path)

    # Build agent
    agent = build_dataset_agent_graph()

    initial_state: DatasetAgentState = {
        "dataset_id": dataset_id,
        "prompt": "From the given DataFrame, first remove all rows where name or sales is missing. Then, for all remaining rows, group the data by region and product, and calculate the total sales, average sales, and count of sales for each group. Make sure the grouping considers all remaining records, without excluding anyone, while keeping the original dataset unchanged.",
        "thread_id": "thread_123",
        "artifact_id": base_artifact_id,
        "new_artifact_id": None,
        "messages": [],
        "python_code_file": None,
    }

    # Streamed execution
    async for mode, chunk in agent.astream(
        initial_state,
        stream_mode=["updates", "values", "messages", "custom"],
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    ):
        print(mode, "→", chunk)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
