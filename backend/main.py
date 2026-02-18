# backend/main.py
import os
import pandas as pd
import json
import asyncio
from datetime import datetime, timezone

from config import DATASET_DIR, ARTIFACT_DIR
from models import DatasetAgentState
from utils import generate_id, save_json, save_dataframe
from graph import build_dataset_agent_graph

# =========================
# Example Usage
# =========================
async def main():
    # Setup example dataset
    dataset_id = generate_id("ds")
    
    df = pd.read_csv("../sample-data/cardiovascular-risk.csv")    
    
    # Save original dataset
    original_file_path = os.path.join(DATASET_DIR, f"{dataset_id}_original.csv")
    df.to_csv(original_file_path, index=False)

    dataset_meta = {
        "id": dataset_id,
        "name": "Cardiovascular Risk Dataset",
        "original_file": original_file_path,
        "schema": list(df.columns),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": "user_1",
        "artifacts": [],
    }

    dataset_meta_path = os.path.join(DATASET_DIR, f"{dataset_id}.json")
    save_json(dataset_meta, dataset_meta_path)

    # Create base artifact
    base_artifact_id = generate_id("artifact")
    save_dataframe(df, base_artifact_id)
    
    artifact_meta = {
        "id": base_artifact_id,
        "dataset_id": dataset_id,
        "thread_id": None,
        "type": "base_dataset",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": [],
        "metadata": {"rows": len(df), "columns": len(df.columns)},
    }
    save_json(artifact_meta, os.path.join(ARTIFACT_DIR, f"{base_artifact_id}.json"))

    dataset_meta["artifacts"].append(base_artifact_id)
    save_json(dataset_meta, dataset_meta_path)

    # Build and run agent
    agent = build_dataset_agent_graph()

    initial_state: DatasetAgentState = {
        "dataset_id": dataset_id,
        "original_prompt": "Visualize pairwise relationships among all numeric health variables, colored by cardiovascular risk.",
        "thread_id": "thread_123",
    }

    print("=" * 80)
    print("AGENTIC DATA PROCESSING SYSTEM - EXECUTION LOG")
    print("=" * 80)

    async for mode, chunk in agent.astream(
        initial_state,
        stream_mode=["updates", "custom"],
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    ):
        if mode == "custom":
            print(f"[STATUS] {chunk}")
        elif mode == "updates":
            for node_name, node_output in chunk.items():
                print(f"\n[NODE: {node_name}]")
                if node_output.get("messages"):
                    for msg in node_output["messages"]:
                        print(f"  {msg}")

    print("\n" + "=" * 80)
    print("EXECUTION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())