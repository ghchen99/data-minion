# backend/api.py
import os
import asyncio
from fastapi import FastAPI, UploadFile, Form
from fastapi.responses import JSONResponse, StreamingResponse
import pandas as pd
from datetime import datetime, timezone
import json

from config import DATASET_DIR, ARTIFACT_DIR, IMAGE_DIR
from utils import generate_id, save_json, save_dataframe, load_json
from graph import build_dataset_agent_graph
from models import DatasetAgentState

from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(title="Agentic Data Processing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload-and-run")
async def upload_and_run(file: UploadFile, prompt: str = Form(...), owner_id: str = Form("user_1")):
    """
    Upload a CSV file and run the LangGraph agent on the provided prompt.
    Returns a structured reflection of execution, artifacts, and deliverables.
    """
    # ----------------------
    # Step 1: Save uploaded CSV
    # ----------------------
    dataset_id = generate_id("ds")
    df = pd.read_csv(file.file)

    original_file_path = os.path.join(DATASET_DIR, f"{dataset_id}_original.csv")
    df.to_csv(original_file_path, index=False)

    dataset_meta = {
        "id": dataset_id,
        "name": f"Dataset {dataset_id}",
        "original_file": original_file_path,
        "schema": list(df.columns),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": owner_id,
        "artifacts": [],
    }
    dataset_meta_path = os.path.join(DATASET_DIR, f"{dataset_id}.json")
    save_json(dataset_meta, dataset_meta_path)

    # ----------------------
    # Step 2: Create base artifact
    # ----------------------
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

    # ----------------------
    # Step 3: Build agent
    # ----------------------
    agent = build_dataset_agent_graph()

    initial_state: DatasetAgentState = {
        "dataset_id": dataset_id,
        "original_prompt": prompt,
        "thread_id": generate_id("thread"),
        "current_step_idx": 0,
        "completed_steps": [],
        "new_artifact_ids": [],
        "tool_history": [],
        "intermediate_artifacts": [],
        "messages": [],
        "retry_count": 0,
        "schema_before": {},
        "schema_after": {},
        "python_code_file": "",
        "analysis_summary": "",
    }

    # ----------------------
    # Step 4: Run agent asynchronously and collect structured logs
    # ----------------------
    execution_flow = []  # structured reflection
    artifacts_collected = []

    async for mode, chunk in agent.astream(
        initial_state,
        stream_mode=["updates", "custom"],
        config={"configurable": {"thread_id": initial_state["thread_id"]}},
    ):
        if mode == "custom":
            execution_flow.append({"status_update": chunk})
        elif mode == "updates":
            for node_name, node_output in chunk.items():
                step_info = {"node": node_name, "messages": [], "artifacts": []}
                # Capture node messages
                if node_output.get("messages"):
                    step_info["messages"].extend(node_output["messages"])
                # Capture new artifacts or visualizations
                new_artifacts = node_output.get("new_artifact_ids", []) or node_output.get("intermediate_artifacts", [])
                step_info["artifacts"].extend(new_artifacts)
                artifacts_collected.extend(new_artifacts)
                execution_flow.append(step_info)

    # ----------------------
    # Step 5: Return structured reflection
    # ----------------------
    response = {
        "dataset_id": dataset_id,
        "base_artifact_id": base_artifact_id,
        "all_artifacts": dataset_meta["artifacts"] + artifacts_collected,
        "execution_flow": execution_flow,
        "final_summary": initial_state.get("analysis_summary", ""),
    }

    return JSONResponse(content=response)

@app.post("/upload-and-run-stream")
async def upload_and_run_stream(file: UploadFile, prompt: str = Form(...), owner_id: str = Form("user_1")):
    """
    Upload CSV and stream agent execution step by step as JSON chunks.
    """
    # Step 1: Save uploaded CSV (same as before)
    dataset_id = generate_id("ds")
    df = pd.read_csv(file.file)
    original_file_path = os.path.join(DATASET_DIR, f"{dataset_id}_original.csv")
    df.to_csv(original_file_path, index=False)

    dataset_meta = {
        "id": dataset_id,
        "name": f"Dataset {dataset_id}",
        "original_file": original_file_path,
        "schema": list(df.columns),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "owner_id": owner_id,
        "artifacts": [],
    }
    dataset_meta_path = os.path.join(DATASET_DIR, f"{dataset_id}.json")
    save_json(dataset_meta, dataset_meta_path)

    # Step 2: Create base artifact
    base_artifact_id = generate_id("artifact")
    save_dataframe(df, base_artifact_id)
    dataset_meta["artifacts"].append(base_artifact_id)
    save_json(dataset_meta, dataset_meta_path)

    # Step 3: Build agent
    agent = build_dataset_agent_graph()
    initial_state: DatasetAgentState = {
        "dataset_id": dataset_id,
        "original_prompt": prompt,
        "thread_id": generate_id("thread"),
        "current_step_idx": 0,
        "completed_steps": [],
        "new_artifact_ids": [],
        "tool_history": [],
        "intermediate_artifacts": [],
        "messages": [],
        "retry_count": 0,
        "schema_before": {},
        "schema_after": {},
        "python_code_file": "",
        "analysis_summary": "",
    }

    async def event_stream():
        """Yield agent updates as JSON lines."""
        async for mode, chunk in agent.astream(
            initial_state,
            stream_mode=["values", "custom", "updates"],
            config={"configurable": {"thread_id": initial_state["thread_id"]}},
        ):
            output = {}
            if mode == "custom":
                output["status_update"] = chunk
            elif mode == "updates":
                output["updates"] = []
                for node_name, node_output in chunk.items():
                    node_info = {
                        "node": node_name,
                        "messages": node_output.get("messages", []),
                        "artifacts": node_output.get("new_artifact_ids", []) or node_output.get("intermediate_artifacts", []),
                    }
                    output["updates"].append(node_info)
            # Yield as a JSON string line with newline separator
            yield json.dumps(output) + "\n"
            await asyncio.sleep(0)  # allow async context switch

        # Final summary at the end
        yield json.dumps({
            "dataset_id": dataset_id,
            "base_artifact_id": base_artifact_id,
            "all_artifacts": dataset_meta["artifacts"] + initial_state.get("new_artifact_ids", []),
            "final_summary": initial_state.get("analysis_summary", ""),
            "completed": True
        }) + "\n"

    return StreamingResponse(event_stream(), media_type="application/json")

@app.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str):
    """
    Fetch artifact details.
    For chart images, returns JSON with file path (can be served via static route in frontend).
    """
    artifact_json_path = os.path.join(ARTIFACT_DIR, f"{artifact_id}.json")
    image_path = os.path.join(IMAGE_DIR, f"{artifact_id}.png")

    if os.path.exists(artifact_json_path):
        data = load_json(artifact_json_path)
        # Include image path if chart
        if artifact_id.startswith("chart_") and os.path.exists(image_path):
            data["image_path"] = f"/static/images/{artifact_id}.png"
        return JSONResponse(content=data)
    else:
        return JSONResponse(status_code=404, content={"error": "Artifact not found"})


# =======================
# Uvicorn Run
# =======================
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
