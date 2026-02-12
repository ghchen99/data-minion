"""
langgraph_data_agent_llm_stream.py

LangGraph Data Agent fully LLM-driven with streaming support,
schema-aware reformulation, and safe execution flow.
"""

from typing import TypedDict, Optional, Dict, Any, List
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langchain.chat_models import init_chat_model

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
    temperature=0,
)

# =========================
# State Definition
# =========================
class DatasetAgentState(TypedDict, total=False):
    dataset_id: str
    prompt: str
    thread_id: str
    artifact_id: str
    new_artifact_id: str
    python_code_file: str
    messages: List[str]
    error: str


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


def build_schema_description(df: pd.DataFrame) -> str:
    df = df.convert_dtypes()

    lines = []
    for col in df.columns:
        dtype = df[col].dtype
        non_null = df[col].notna().sum()
        lines.append(f"- {col} ({dtype}), non-null values: {non_null}")

    return "\n".join(lines)


# =========================
# Nodes
# =========================
async def load_latest_dataset(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    writer({"status": "Loading latest dataset artifact..."})

    dataset_meta_path = os.path.join(DATASET_DIR, f"{state['dataset_id']}.json")
    dataset_meta = load_json(dataset_meta_path)
    latest_artifact_id = dataset_meta["artifacts"][-1]

    writer({"status": f"Loaded artifact {latest_artifact_id}"})
    return {"artifact_id": latest_artifact_id}


async def reformulate_prompt(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    writer({"status": "Reformulating user prompt using dataset schema..."})

    df = load_dataframe(state["artifact_id"])
    schema_text = build_schema_description(df)

    llm_prompt = f"""
You are a professional data analyst.

Dataset schema:
{schema_text}

Number of rows: {len(df)}

User request:
"{state['prompt']}"

Rewrite the request so it:
- Explicitly references column names
- Mentions relevant data types
- Clarifies ambiguous language
- Remains natural language (NOT code)
- Is concise but precise

Return only the rewritten instruction.
"""

    response = await model.ainvoke(llm_prompt)
    reformulated = response.content.strip()

    writer({"status": "Prompt reformulated successfully"})
    return {"prompt": reformulated}


async def llm_generate_python_code(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    writer({"status": "Generating Python code..."})

    df = load_dataframe(state["artifact_id"])
    schema_text = build_schema_description(df)

    llm_prompt = f"""
You are a senior Python pandas engineer.

Dataset schema:
{schema_text}

Number of rows: {len(df)}

Task:
{state['prompt']}

Rules:
- Modify only the DataFrame variable `df`
- Do NOT print anything
- Do NOT return anything
- Use pandas only
- Do NOT include markdown backticks
"""

    response = await model.ainvoke(llm_prompt)
    code = response.content.strip()

    code_file = save_python_code(code, state["artifact_id"])

    writer({"status": "Python code generated"})
    return {"python_code_file": code_file}


async def execute_python_code(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    writer({"status": "Executing generated Python code..."})

    df = load_dataframe(state["artifact_id"])
    local_ns = {"df": df, "pd": pd}

    try:
        # Read and exec generated code
        with open(state["python_code_file"]) as f:
            code = f.read()
        exec(code, {}, local_ns)

        # Find all DataFrame variables
        df_vars = [v for v in local_ns.values() if isinstance(v, pd.DataFrame)]
        if not df_vars:
            raise ValueError("No DataFrame found in generated code execution.")

        # Take the last one
        new_df = df_vars[-1]

    except Exception as e:
        writer({"status": f"Execution error: {e}"})
        return {"error": str(e)}

    # Save the resulting DataFrame as the artifact
    save_dataframe(new_df, state["artifact_id"])
    writer({"status": "Code executed successfully"})
    return {}



async def register_artifact(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()

    if state.get("error"):
        writer({"status": "Skipping artifact registration due to execution error."})
        return {}

    df = load_dataframe(state["artifact_id"])
    new_artifact_id = generate_id("artifact")

    save_dataframe(df, new_artifact_id)

    artifact_meta = {
        "id": new_artifact_id,
        "dataset_id": state["dataset_id"],
        "thread_id": state["thread_id"],
        "type": "derived_dataset",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": [state["artifact_id"]],
        "metadata": {"rows": len(df)},
    }

    save_json(artifact_meta, os.path.join(ARTIFACT_DIR, f"{new_artifact_id}.json"))

    dataset_meta_path = os.path.join(DATASET_DIR, f"{state['dataset_id']}.json")
    dataset_meta = load_json(dataset_meta_path)
    dataset_meta["artifacts"].append(new_artifact_id)
    save_json(dataset_meta, dataset_meta_path)

    writer({"status": f"Registered new artifact {new_artifact_id}"})
    return {"new_artifact_id": new_artifact_id}


async def summarize_artifact(state: DatasetAgentState) -> Dict:
    if state.get("error"):
        return {"messages": [f"Execution failed: {state['error']}"]}

    df = load_dataframe(state["new_artifact_id"])
    preview = df.head().to_dict(orient="records")

    return {"messages": [f"Preview: {preview}"]}


# =========================
# Graph Construction
# =========================
def build_dataset_agent_graph():
    workflow = StateGraph(DatasetAgentState)

    workflow.add_node("load_latest_dataset", load_latest_dataset)
    workflow.add_node("reformulate_prompt", reformulate_prompt)
    workflow.add_node("llm_generate_python_code", llm_generate_python_code)
    workflow.add_node("execute_python_code", execute_python_code)
    workflow.add_node("register_artifact", register_artifact)
    workflow.add_node("summarize_artifact", summarize_artifact)

    workflow.add_edge(START, "load_latest_dataset")
    workflow.add_edge("load_latest_dataset", "reformulate_prompt")
    workflow.add_edge("reformulate_prompt", "llm_generate_python_code")
    workflow.add_edge("llm_generate_python_code", "execute_python_code")
    workflow.add_edge("execute_python_code", "register_artifact")
    workflow.add_edge("register_artifact", "summarize_artifact")
    workflow.add_edge("summarize_artifact", END)

    return workflow.compile(checkpointer=MemorySaver())


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
        # stream_mode=["updates", "values", "messages", "custom"],
        stream_mode=["updates", "custom"],
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    ):
        print(mode, "→", chunk)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
