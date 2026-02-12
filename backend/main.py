"""
langgraph_data_agent_improved.py

Production-grade LangGraph Data Agent with:
- Planning/Task Decomposition
- Error Recovery Loop
- Multi-artifact support (CSV, charts, reports)
- Schema validation
- Tool routing
- Comprehensive state tracking
"""

from typing import TypedDict, Optional, Dict, Any, List, Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.config import get_stream_writer
from langchain.chat_models import init_chat_model
from pydantic import BaseModel, Field

import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
import uuid
import hashlib
from datetime import datetime, timezone
import os
import json
from dotenv import load_dotenv
import operator

# =========================
# Config
# =========================
BASE_STORAGE_DIR = "data_agent_storage"
DATASET_DIR = os.path.join(BASE_STORAGE_DIR, "datasets")
ARTIFACT_DIR = os.path.join(BASE_STORAGE_DIR, "artifacts")
CODE_DIR = os.path.join(BASE_STORAGE_DIR, "python_code")
IMAGE_DIR = os.path.join(BASE_STORAGE_DIR, "images")
REPORT_DIR = os.path.join(BASE_STORAGE_DIR, "reports")

for d in [DATASET_DIR, ARTIFACT_DIR, CODE_DIR, IMAGE_DIR, REPORT_DIR]:
    os.makedirs(d, exist_ok=True)

# =========================
# Load environment variables and init LLM
# =========================
load_dotenv()

model = init_chat_model(
    "azure_openai:gpt-4o",
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    temperature=0,
)

# =========================
# Pydantic Models for Structured Outputs
# =========================
class TaskStep(BaseModel):
    """Single step in the execution plan"""
    step_id: str = Field(description="Unique identifier for this step")
    description: str = Field(description="What this step does")
    task_type: Literal["transformation", "aggregation", "cleaning", "feature_engineering", "visualization", "analysis"]
    requires_code: bool = Field(description="Whether this step needs code execution")
    requires_visualization: bool = Field(description="Whether this step produces a chart")
    depends_on: List[str] = Field(default_factory=list, description="IDs of steps this depends on")


class ExecutionPlan(BaseModel):
    """Structured task plan"""
    clarified_request: str = Field(description="Clarified version of user request")
    columns_used: List[str] = Field(description="Columns referenced in the task")
    steps: List[TaskStep] = Field(description="Ordered list of execution steps")
    assumptions: List[str] = Field(description="Assumptions made during planning")


class ReformulatedTask(BaseModel):
    """Structured reformulation output"""
    clarified_task: str
    columns_used: List[str]
    operations: List[str]
    assumptions: List[str]


class SchemaChange(BaseModel):
    """Schema validation result"""
    columns_added: List[str] = Field(default_factory=list)
    columns_removed: List[str] = Field(default_factory=list)
    dtypes_changed: Dict[str, str] = Field(default_factory=dict)
    row_count_change: int = Field(default=0)
    is_intentional: bool = Field(default=True)


class ToolRoute(BaseModel):
    """Tool selection decision"""
    primary_tool: Literal["pandas", "visualization", "profiling", "explanation"]
    needs_execution: bool
    rationale: str


# =========================
# State Definition
# =========================
class DatasetAgentState(TypedDict, total=False):
    # Core identifiers
    dataset_id: str
    thread_id: str
    artifact_id: str
    
    # User input
    original_prompt: str
    
    # Planning state
    plan: Optional[ExecutionPlan]
    current_step_idx: int
    completed_steps: Annotated[List[str], operator.add]
    
    # Execution state
    reformulated_prompt: str
    tool_route: Optional[ToolRoute]
    python_code_file: str
    execution_error: Optional[str]
    retry_count: int
    
    # Schema tracking
    schema_before: Dict[str, Any]
    schema_after: Dict[str, Any]
    schema_validation: Optional[SchemaChange]
    
    # Artifacts
    new_artifact_ids: Annotated[List[str], operator.add]
    tool_history: Annotated[List[Dict], operator.add]
    intermediate_artifacts: Annotated[List[str], operator.add]
    
    # Output
    messages: Annotated[List[str], operator.add]
    analysis_summary: str


# =========================
# Helpers
# =========================
def generate_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def compute_code_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()[:16]


def save_json(obj: dict, path: str):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


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


def save_python_code(code: str, code_id: str) -> str:
    path = os.path.join(CODE_DIR, f"{code_id}.py")
    with open(path, "w") as f:
        f.write(code)
    return path


def build_schema_description(df: pd.DataFrame) -> str:
    df = df.convert_dtypes()
    lines = []
    for col in df.columns:
        dtype = df[col].dtype
        non_null = df[col].notna().sum()
        null_count = df[col].isna().sum()
        lines.append(f"- {col} ({dtype}), non-null: {non_null}, null: {null_count}")
    return "\n".join(lines)


def extract_schema(df: pd.DataFrame) -> Dict[str, Any]:
    """Extract schema metadata for comparison"""
    return {
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "row_count": len(df),
        "null_counts": df.isnull().sum().to_dict()
    }


def compare_schemas(before: Dict, after: Dict) -> SchemaChange:
    """Compare two schemas and detect changes"""
    cols_before = set(before["columns"])
    cols_after = set(after["columns"])
    
    added = list(cols_after - cols_before)
    removed = list(cols_before - cols_after)
    
    dtype_changes = {}
    for col in cols_before & cols_after:
        if before["dtypes"][col] != after["dtypes"][col]:
            dtype_changes[col] = f"{before['dtypes'][col]} → {after['dtypes'][col]}"
    
    row_change = after["row_count"] - before["row_count"]
    
    return SchemaChange(
        columns_added=added,
        columns_removed=removed,
        dtypes_changed=dtype_changes,
        row_count_change=row_change
    )


# =========================
# Nodes
# =========================
async def load_latest_dataset(state: DatasetAgentState) -> Dict:
    writer = get_stream_writer()
    writer({"status": "Loading latest dataset artifact..."})

    dataset_meta_path = os.path.join(DATASET_DIR, f"{state['dataset_id']}.json")
    dataset_meta = load_json(dataset_meta_path)
    latest_artifact_id = dataset_meta["artifacts"][-1]

    df = load_dataframe(latest_artifact_id)
    schema = extract_schema(df)

    writer({"status": f"Loaded artifact {latest_artifact_id} with {len(df)} rows"})
    
    return {
        "artifact_id": latest_artifact_id,
        "schema_before": schema,
        "retry_count": 0,
        "current_step_idx": 0
    }


async def plan_task(state: DatasetAgentState) -> Dict:
    """Orchestrator node: breaks down request into structured plan"""
    writer = get_stream_writer()
    writer({"status": "Planning task decomposition..."})

    df = load_dataframe(state["artifact_id"])
    schema_text = build_schema_description(df)

    planner = model.with_structured_output(ExecutionPlan)
    
    llm_prompt = f"""
You are a data task planner. Break down the user's request into atomic steps.

Dataset schema:
{schema_text}

Number of rows: {len(df)}

User request:
"{state['original_prompt']}"

Create a structured execution plan that:
1. Clarifies the request with explicit column names
2. Identifies all columns that will be used
3. Breaks the task into atomic steps (cleaning, transformation, aggregation, visualization, etc.)
4. Specifies which steps need code execution vs. are explanation-only
5. Notes any assumptions you're making

Each step should be independent and have clear dependencies.
"""

    plan = await planner.ainvoke(llm_prompt)
    
    writer({"status": f"Plan created with {len(plan.steps)} steps"})
    writer({"plan": plan.model_dump()})
    
    return {"plan": plan}


async def route_tool(state: DatasetAgentState) -> Dict:
    """Decide which tool/approach to use for current step"""
    writer = get_stream_writer()
    
    current_step = state["plan"].steps[state["current_step_idx"]]
    writer({"status": f"Routing tool for step: {current_step.description}"})
    
    router = model.with_structured_output(ToolRoute)
    
    llm_prompt = f"""
Analyze this task step and decide which tool to use.

Step: {current_step.description}
Task type: {current_step.task_type}

Available tools:
- pandas: Data transformation, filtering, grouping, aggregation
- visualization: Creating charts (matplotlib/seaborn)
- profiling: Dataset statistics and summary
- explanation: No code needed, just analysis/explanation

Return the primary tool and whether code execution is needed.
"""

    route = await router.ainvoke(llm_prompt)
    
    writer({"status": f"Selected tool: {route.primary_tool}"})
    
    return {"tool_route": route}


async def should_execute_code(state: DatasetAgentState) -> str:
    """Conditional edge: determine if code execution is needed"""
    if state["tool_route"].needs_execution:
        return "generate_code"
    else:
        return "explain_only"


async def reformulate_prompt(state: DatasetAgentState) -> Dict:
    """Convert current step into precise, schema-aware instruction"""
    writer = get_stream_writer()
    writer({"status": "Reformulating step with schema context..."})

    df = load_dataframe(state["artifact_id"])
    schema_text = build_schema_description(df)
    
    current_step = state["plan"].steps[state["current_step_idx"]]
    
    reformulator = model.with_structured_output(ReformulatedTask)

    llm_prompt = f"""
You are refining a data task instruction.

Dataset schema:
{schema_text}

Step to execute:
{current_step.description}

Rewrite this step to:
- Explicitly reference column names from the schema
- Mention relevant data types
- Clarify any ambiguous operations
- List specific operations (filter, group, aggregate, etc.)
- Note assumptions

Return structured output with clarified task, columns used, operations, and assumptions.
"""

    reformulated = await reformulator.ainvoke(llm_prompt)
    
    writer({"status": "Step reformulated with explicit column references"})
    
    return {"reformulated_prompt": reformulated.clarified_task}


async def generate_python_code(state: DatasetAgentState) -> Dict:
    """Generate code based on tool route and reformulated prompt"""
    writer = get_stream_writer()
    writer({"status": f"Generating {state['tool_route'].primary_tool} code..."})

    df = load_dataframe(state["artifact_id"])
    schema_text = build_schema_description(df)
    
    current_step = state["plan"].steps[state["current_step_idx"]]

    # Different prompts based on tool type
    if state["tool_route"].primary_tool == "visualization":
        code_prompt = f"""
You are a data visualization expert using matplotlib and seaborn.

Dataset schema:
{schema_text}

Number of rows: {len(df)}

Task:
{state['reformulated_prompt']}

Generate Python code that:
- Loads the DataFrame as `df`
- Creates visualization using matplotlib/seaborn
- Saves the figure to a variable `fig`
- Does NOT call plt.show()
- Does NOT print anything

Return only clean Python code, no markdown backticks.
"""
    else:
        code_prompt = f"""
You are a senior Python pandas engineer.

Dataset schema:
{schema_text}

Number of rows: {len(df)}

Task:
{state['reformulated_prompt']}

Generate Python code that:
- Modifies the DataFrame variable `df` in-place
- Does NOT print anything
- Does NOT return anything
- Uses only pandas operations
- Handles edge cases (null values, etc.)

Return only clean Python code, no markdown backticks.
"""

    response = await model.ainvoke(code_prompt)
    code = response.content.strip()
    
    # Remove markdown backticks if present
    if code.startswith("```python"):
        code = code.split("```python")[1].split("```")[0].strip()
    elif code.startswith("```"):
        code = code.split("```")[1].split("```")[0].strip()
    
    code_id = f"{state['artifact_id']}_{current_step.step_id}"
    code_file = save_python_code(code, code_id)
    code_hash = compute_code_hash(code)

    writer({"status": f"Code generated (hash: {code_hash})"})
    
    # Log to tool history
    tool_log = {
        "step_id": current_step.step_id,
        "tool": state['tool_route'].primary_tool,
        "code_file": code_file,
        "code_hash": code_hash,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    return {
        "python_code_file": code_file,
        "tool_history": [tool_log]
    }


async def execute_python_code(state: DatasetAgentState) -> Dict:
    """Execute generated code with error handling"""
    writer = get_stream_writer()
    writer({"status": "Executing generated code..."})

    df = load_dataframe(state["artifact_id"])
    current_step = state["plan"].steps[state["current_step_idx"]]
    
    # Prepare execution namespace
    local_ns = {
        "df": df.copy(),  # Work on a copy
        "pd": pd,
        "plt": plt,
        "sns": sns,
        "fig": None
    }

    try:
        with open(state["python_code_file"]) as f:
            code = f.read()
        
        exec(code, {}, local_ns)

        # Handle visualization artifacts
        if state["tool_route"].primary_tool == "visualization":
            if local_ns.get("fig") is not None:
                # Save figure
                img_id = generate_id("chart")
                img_path = os.path.join(IMAGE_DIR, f"{img_id}.png")
                local_ns["fig"].savefig(img_path, dpi=150, bbox_inches='tight')
                plt.close(local_ns["fig"])
                
                writer({"status": f"Chart saved: {img_id}.png"})
                
                return {
                    "intermediate_artifacts": [img_id],
                    "execution_error": None,
                    "schema_after": state["schema_before"]  # No schema change for viz
                }
            else:
                raise ValueError("Visualization code did not produce a 'fig' variable")
        
        # Handle data transformation artifacts
        else:
            # Find the modified DataFrame
            df_vars = [v for v in local_ns.values() if isinstance(v, pd.DataFrame)]
            if not df_vars:
                raise ValueError("No DataFrame found after code execution")
            
            result_df = df_vars[-1]  # Take the last one
            
            # Extract schema after execution
            schema_after = extract_schema(result_df)
            
            # Save transformed data back to artifact
            save_dataframe(result_df, state["artifact_id"])
            
            writer({"status": f"Code executed successfully, {len(result_df)} rows"})
            
            return {
                "schema_after": schema_after,
                "execution_error": None
            }

    except Exception as e:
        writer({"status": f"Execution error: {str(e)}"})
        return {
            "execution_error": str(e),
            "schema_after": state["schema_before"]
        }


async def validate_schema_change(state: DatasetAgentState) -> Dict:
    """Check if schema changes were intentional"""
    writer = get_stream_writer()
    
    if state.get("execution_error"):
        writer({"status": "Skipping schema validation due to execution error"})
        return {}
    
    schema_change = compare_schemas(state["schema_before"], state["schema_after"])
    
    # If no significant changes, skip validation
    if (not schema_change.columns_added and 
        not schema_change.columns_removed and 
        not schema_change.dtypes_changed):
        writer({"status": "No schema changes detected"})
        return {"schema_validation": schema_change}
    
    writer({"status": "Validating schema changes..."})
    
    # Ask LLM if changes were intentional
    llm_prompt = f"""
Analyze if these schema changes were intentional for the given task.

Original task: {state['reformulated_prompt']}

Schema changes detected:
- Columns added: {schema_change.columns_added}
- Columns removed: {schema_change.columns_removed}
- Data types changed: {schema_change.dtypes_changed}
- Row count change: {schema_change.row_count_change}

Were these changes intentional and correct? Answer 'yes' or 'no' and explain briefly.
"""

    response = await model.ainvoke(llm_prompt)
    is_intentional = "yes" in response.content.lower()
    
    schema_change.is_intentional = is_intentional
    
    if not is_intentional:
        writer({"status": "⚠️ Unintentional schema changes detected"})
    else:
        writer({"status": "✓ Schema changes validated as intentional"})
    
    return {"schema_validation": schema_change}


async def check_execution_success(state: DatasetAgentState) -> str:
    """Conditional edge: retry on error or proceed"""
    if state.get("execution_error") and state["retry_count"] < 2:
        return "fix_code"
    elif state.get("execution_error"):
        return "error_summary"
    else:
        return "mark_complete"


async def fix_code_with_error(state: DatasetAgentState) -> Dict:
    """Self-healing: regenerate code based on error feedback"""
    writer = get_stream_writer()
    writer({"status": f"Attempting to fix code (retry {state['retry_count'] + 1}/2)..."})

    df = load_dataframe(state["artifact_id"])
    schema_text = build_schema_description(df)
    
    # Read the failed code
    with open(state["python_code_file"]) as f:
        failed_code = f.read()

    llm_prompt = f"""
You are debugging Python pandas code that failed.

Dataset schema:
{schema_text}

Original task:
{state['reformulated_prompt']}

Failed code:
```python
{failed_code}
```

Error message:
{state['execution_error']}

Fix the code to handle this error. Common issues:
- Missing null value handling
- Wrong column names
- Type mismatches
- Index issues

Return only the corrected Python code, no markdown backticks.
"""

    response = await model.ainvoke(llm_prompt)
    fixed_code = response.content.strip()
    
    if fixed_code.startswith("```python"):
        fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
    elif fixed_code.startswith("```"):
        fixed_code = fixed_code.split("```")[1].split("```")[0].strip()
    
    # Save fixed code
    current_step = state["plan"].steps[state["current_step_idx"]]
    code_id = f"{state['artifact_id']}_{current_step.step_id}_retry{state['retry_count'] + 1}"
    code_file = save_python_code(fixed_code, code_id)
    
    writer({"status": "Code regenerated with error fix"})
    
    return {
        "python_code_file": code_file,
        "retry_count": state["retry_count"] + 1
    }


async def mark_step_complete(state: DatasetAgentState) -> Dict:
    """Mark current step as complete and prepare for next"""
    writer = get_stream_writer()
    
    current_step = state["plan"].steps[state["current_step_idx"]]
    writer({"status": f"✓ Step complete: {current_step.description}"})
    
    return {
        "completed_steps": [current_step.step_id],
        "current_step_idx": state["current_step_idx"] + 1,
        "retry_count": 0,  # Reset retry counter for next step
        "schema_before": state["schema_after"]  # Current state becomes baseline
    }


async def check_more_steps(state: DatasetAgentState) -> str:
    """Conditional edge: continue to next step or finalize"""
    if state["current_step_idx"] < len(state["plan"].steps):
        return "route_tool"
    else:
        return "register_artifacts"


async def explain_only_node(state: DatasetAgentState) -> Dict:
    """Handle explanation-only steps (no code execution)"""
    writer = get_stream_writer()
    writer({"status": "Generating explanation..."})
    
    df = load_dataframe(state["artifact_id"])
    current_step = state["plan"].steps[state["current_step_idx"]]
    
    llm_prompt = f"""
Provide a clear explanation for this analysis step.

Current data: {len(df)} rows
Step: {current_step.description}

Give a concise explanation of what would be done and why.
"""

    response = await model.ainvoke(llm_prompt)
    
    writer({"status": f"Explanation: {response.content[:100]}..."})
    
    return {
        "messages": [f"Step {current_step.step_id}: {response.content}"]
    }


async def register_artifacts(state: DatasetAgentState) -> Dict:
    """Register all generated artifacts with metadata"""
    writer = get_stream_writer()
    writer({"status": "Registering artifacts..."})

    if state.get("execution_error"):
        writer({"status": "Skipping artifact registration due to errors"})
        return {}

    # Register main data artifact
    df = load_dataframe(state["artifact_id"])
    new_artifact_id = generate_id("artifact")
    save_dataframe(df, new_artifact_id)

    # Build comprehensive metadata
    artifact_meta = {
        "id": new_artifact_id,
        "dataset_id": state["dataset_id"],
        "thread_id": state["thread_id"],
        "type": "derived_dataset",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": [state["artifact_id"]],
        "transformation_type": "multi_step_plan",
        "plan_summary": state["plan"].clarified_request,
        "steps_executed": state["completed_steps"],
        "tool_history": state.get("tool_history", []),
        "schema": extract_schema(df),
        "metadata": {
            "rows": len(df),
            "columns": len(df.columns),
            "plan_steps": len(state["plan"].steps)
        }
    }

    artifact_path = os.path.join(ARTIFACT_DIR, f"{new_artifact_id}.json")
    save_json(artifact_meta, artifact_path)

    # Update dataset metadata
    dataset_meta_path = os.path.join(DATASET_DIR, f"{state['dataset_id']}.json")
    dataset_meta = load_json(dataset_meta_path)
    dataset_meta["artifacts"].append(new_artifact_id)
    save_json(dataset_meta, dataset_meta_path)

    # Register visualization artifacts if any
    viz_artifacts = []
    for img_id in state.get("intermediate_artifacts", []):
        viz_meta = {
            "id": img_id,
            "type": "chart",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "related_to": new_artifact_id
        }
        viz_path = os.path.join(IMAGE_DIR, f"{img_id}.json")
        save_json(viz_meta, viz_path)
        viz_artifacts.append(img_id)

    writer({"status": f"✓ Registered artifact {new_artifact_id}"})
    if viz_artifacts:
        writer({"status": f"✓ Registered {len(viz_artifacts)} visualizations"})

    return {
        "new_artifact_ids": [new_artifact_id] + viz_artifacts
    }


async def generate_summary(state: DatasetAgentState) -> Dict:
    """Generate final analysis summary"""
    writer = get_stream_writer()
    
    if state.get("execution_error"):
        return {
            "messages": [f"❌ Execution failed after retries: {state['execution_error']}"],
            "analysis_summary": "Task failed due to execution errors."
        }

    df = load_dataframe(state["artifact_id"])
    
    summary_parts = [
        f"✓ Task completed successfully",
        f"✓ Executed {len(state['completed_steps'])} steps",
        f"✓ Final dataset: {len(df)} rows × {len(df.columns)} columns",
    ]
    
    if state.get("new_artifact_ids"):
        summary_parts.append(f"✓ Generated {len(state['new_artifact_ids'])} artifacts")
    
    # Schema changes summary
    if state.get("schema_validation"):
        sc = state["schema_validation"]
        if sc.columns_added:
            summary_parts.append(f"  - Added columns: {', '.join(sc.columns_added)}")
        if sc.columns_removed:
            summary_parts.append(f"  - Removed columns: {', '.join(sc.columns_removed)}")
        if sc.row_count_change != 0:
            summary_parts.append(f"  - Row count change: {sc.row_count_change:+d}")
    
    # Data preview
    preview = df.head(3).to_dict(orient="records")
    summary_parts.append(f"\nPreview:\n{json.dumps(preview, indent=2)}")
    
    summary = "\n".join(summary_parts)
    
    writer({"status": "Summary generated"})
    
    return {
        "messages": [summary],
        "analysis_summary": summary
    }


async def error_summary_node(state: DatasetAgentState) -> Dict:
    """Generate error summary after failed retries"""
    return {
        "messages": [
            f"❌ Task failed after {state['retry_count']} retry attempts",
            f"Error: {state['execution_error']}",
            "Please review the request and try again."
        ],
        "analysis_summary": f"Failed: {state['execution_error']}"
    }


# =========================
# Graph Construction
# =========================
def build_dataset_agent_graph():
    """Build the orchestrator-worker pattern graph with error recovery"""
    workflow = StateGraph(DatasetAgentState)

    # Add all nodes
    workflow.add_node("load_latest_dataset", load_latest_dataset)
    workflow.add_node("plan_task", plan_task)
    workflow.add_node("route_tool", route_tool)
    workflow.add_node("reformulate_prompt", reformulate_prompt)
    workflow.add_node("generate_code", generate_python_code)
    workflow.add_node("execute_code", execute_python_code)
    workflow.add_node("validate_schema", validate_schema_change)
    workflow.add_node("fix_code", fix_code_with_error)
    workflow.add_node("explain_only", explain_only_node)
    workflow.add_node("mark_complete", mark_step_complete)
    workflow.add_node("register_artifacts", register_artifacts)
    workflow.add_node("generate_summary", generate_summary)
    workflow.add_node("error_summary", error_summary_node)

    # Build the flow
    workflow.add_edge(START, "load_latest_dataset")
    workflow.add_edge("load_latest_dataset", "plan_task")
    workflow.add_edge("plan_task", "route_tool")
    
    # Conditional: code execution or explanation
    workflow.add_conditional_edges(
        "route_tool",
        should_execute_code,
        {
            "generate_code": "reformulate_prompt",
            "explain_only": "explain_only"
        }
    )
    
    workflow.add_edge("explain_only", "mark_complete")
    
    # Code generation flow
    workflow.add_edge("reformulate_prompt", "generate_code")
    workflow.add_edge("generate_code", "execute_code")
    workflow.add_edge("execute_code", "validate_schema")
    
    # Conditional: retry on error or proceed
    workflow.add_conditional_edges(
        "validate_schema",
        check_execution_success,
        {
            "fix_code": "fix_code",
            "error_summary": "error_summary",
            "mark_complete": "mark_complete"
        }
    )
    
    # Retry loop
    workflow.add_edge("fix_code", "execute_code")
    
    # Step completion check
    workflow.add_conditional_edges(
        "mark_complete",
        check_more_steps,
        {
            "route_tool": "route_tool",
            "register_artifacts": "register_artifacts"
        }
    )
    
    workflow.add_edge("register_artifacts", "generate_summary")
    workflow.add_edge("generate_summary", END)
    workflow.add_edge("error_summary", END)

    return workflow.compile(checkpointer=MemorySaver())


# =========================
# Example Usage
# =========================
async def main():
    # Setup example dataset
    dataset_id = generate_id("ds")
    
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
    
    # Save original dataset
    original_file_path = os.path.join(DATASET_DIR, f"{dataset_id}_original.csv")
    df.to_csv(original_file_path, index=False)

    dataset_meta = {
        "id": dataset_id,
        "name": "Sales Demo Dataset",
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
        "original_prompt": "Create a new column 'sales_category' that labels sales as 'Low' (<100), 'Medium' (100-200), or 'High' (>200), then create a bar chart showing the count of each category by region.",
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
    import asyncio
    asyncio.run(main())