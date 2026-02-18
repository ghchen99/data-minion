# backend/nodes.py
import os
import json
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timezone
from typing import Dict, Any

from langgraph.config import get_stream_writer
from config import model, DATASET_DIR, ARTIFACT_DIR, IMAGE_DIR
from models import (
    DatasetAgentState, ExecutionPlan, ToolRoute, ReformulatedTask, SchemaChange
)
from utils import (
    load_json, load_dataframe, extract_schema, build_schema_description,
    generate_id, save_dataframe, save_json, compare_schemas, compute_code_hash,
    save_python_code
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
        code_prompt = f"""You are a data visualization expert. Create a publication-quality plot using matplotlib and seaborn.

Dataset schema:
{schema_text}
Rows: {len(df)}

Task: {state['reformulated_prompt']}

Requirements:
- Import necessary libraries (matplotlib.pyplot as plt, seaborn as sns, pandas as pd, numpy as np if needed)
- Use the existing DataFrame variable `df` - it is already loaded
- CRITICAL: Do NOT create sample data or mock DataFrames - work with the provided `df` variable
- Handle categorical filters robustly: normalize strings with .str.lower()/.str.strip() before comparison
- Use sns.set_theme(style="whitegrid", context="talk") and apply a clean, professional, and readable color palette (e.g., "deep", "muted", or "colorblind") appropriate for the data and audience.
- Choose appropriate plot type for the data (e.g., sns.scatterplot, sns.barplot, sns.lineplot, sns.heatmap, sns.violinplot)
- Set clear title, axis labels, and legend where appropriate
- Handle categorical vs numerical data appropriately
- Save figure to variable `fig` using `fig = plt.gcf()` or `fig, ax = plt.subplots()`
- Do NOT call plt.show() or print anything

Return only executable Python code, no markdown backticks or explanations."""

    else:
        code_prompt = f"""You are an expert pandas engineer. Write robust, idiomatic pandas code.

Dataset schema:
{schema_text}
Rows: {len(df)}

Task: {state['reformulated_prompt']}

Requirements:
- Import pandas as pd and numpy as np if needed
- Use the existing DataFrame variable `df` - it is already loaded
- CRITICAL: Do NOT create sample data or mock DataFrames - work with the provided `df` variable
- Perform all transformations on `df` and assign your final result to `result_df`
- CRITICAL: Always assign the final DataFrame to a variable named `result_df`
- Handle missing values explicitly (dropna, fillna, or handle appropriately for the task)
- Use vectorized operations (avoid loops)
- Handle edge cases: empty groups, division by zero, type mismatches
- Use appropriate dtypes (convert strings to datetime/category if beneficial)
- Chain operations efficiently using method chaining where readable
- Do NOT print, display, or return anything

Return only executable Python code, no markdown backticks or explanations."""

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
    """Execute generated code with error handling - FIXED to create intermediate artifacts"""
    writer = get_stream_writer()
    writer({"status": "Executing generated code..."})

    df = load_dataframe(state["artifact_id"])
    current_step = state["plan"].steps[state["current_step_idx"]]
    
    # Prepare execution namespace
    local_ns = {
        "df": df.copy(),  # Work on a copy
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "fig": None
    }

    try:
        with open(state["python_code_file"]) as f:
            code = f.read()
        
        exec(code, local_ns)

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
        
        # Handle data transformation artifacts - FIXED: Create new intermediate artifact
        else:
            # Find the modified DataFrame
            df_vars = [v for v in local_ns.values() if isinstance(v, pd.DataFrame)]
            if not df_vars:
                raise ValueError("No DataFrame found after code execution")
            
            result_df = local_ns.get("result_df")
            
            # Extract schema after execution
            schema_after = extract_schema(result_df)
            
            # FIXED: Create NEW intermediate artifact instead of overwriting input
            intermediate_artifact_id = generate_id("intermediate")
            save_dataframe(result_df, intermediate_artifact_id)
            
            # Save metadata for this intermediate artifact
            intermediate_meta = {
                "id": intermediate_artifact_id,
                "dataset_id": state["dataset_id"],
                "thread_id": state["thread_id"],
                "type": "intermediate_artifact",
                "step_id": current_step.step_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "parent_artifact": state["artifact_id"],
                "schema": schema_after
            }
            save_json(intermediate_meta, os.path.join(ARTIFACT_DIR, f"{intermediate_artifact_id}.json"))
            
            writer({"status": f"Code executed successfully, {len(result_df)} rows"})
            writer({"status": f"Created intermediate artifact: {intermediate_artifact_id}"})

            try:
                if len(result_df) == 0:
                    error_msg = (
                        f"Code execution dropped all {len(df)} rows. "
                        "Likely caused by case-sensitive filtering. "
                        "Normalize values before filtering: df['col'].str.lower().isin({'yes','no'})"
                    )
                    writer({"status": f"⚠️ {error_msg}"})
                    return {
                        "execution_error": error_msg,
                        "schema_after": state["schema_before"],
                        "intermediate_artifacts": [],
                        "artifact_id": state.get("artifact_id")  # fallback to original
                    }
            except Exception as e:
                return {
                    "execution_error": str(e),
                    "schema_after": state["schema_before"],
                    "intermediate_artifacts": [],
                    "artifact_id": state.get("artifact_id")
                }
            
            return {
                "artifact_id": intermediate_artifact_id,  # FIXED: Update state to point to new artifact
                "schema_after": schema_after,
                "execution_error": None,
                "intermediate_artifacts": [intermediate_artifact_id]
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
    
    # Treat unintentional schema changes as a fixable error
    schema_val = state.get("schema_validation")
    if schema_val and not schema_val.is_intentional and state["retry_count"] < 2:
        # Inject a descriptive error so fix_code_with_error has context
        state["execution_error"] = (
            f"Unintentional schema change detected: "
            f"added={schema_val.columns_added}, "
            f"removed={schema_val.columns_removed}, "
            f"dtype changes={schema_val.dtypes_changed}. "
            f"Please fix the code to avoid unintended schema modifications."
        )
        return "fix_code"
    
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

    # The current artifact_id now points to the final transformed data
    df = load_dataframe(state["artifact_id"])
    
    # Create a final artifact with complete metadata
    final_artifact_id = generate_id("artifact")
    save_dataframe(df, final_artifact_id)

    # Build comprehensive metadata
    artifact_meta = {
        "id": final_artifact_id,
        "dataset_id": state["dataset_id"],
        "thread_id": state["thread_id"],
        "type": "derived_dataset",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "lineage": state.get("intermediate_artifacts", []),  # Track all intermediate steps
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

    artifact_path = os.path.join(ARTIFACT_DIR, f"{final_artifact_id}.json")
    save_json(artifact_meta, artifact_path)

    # Update dataset metadata
    dataset_meta_path = os.path.join(DATASET_DIR, f"{state['dataset_id']}.json")
    dataset_meta = load_json(dataset_meta_path)
    dataset_meta["artifacts"].append(final_artifact_id)
    save_json(dataset_meta, dataset_meta_path)

    # Register visualization artifacts if any
    viz_artifacts = [a for a in state.get("intermediate_artifacts", []) if a.startswith("chart_")]
    for img_id in viz_artifacts:
        viz_meta = {
            "id": img_id,
            "type": "chart",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "related_to": final_artifact_id
        }
        viz_path = os.path.join(IMAGE_DIR, f"{img_id}.json")
        save_json(viz_meta, viz_path)

    writer({"status": f"✓ Registered final artifact {final_artifact_id}"})
    if viz_artifacts:
        writer({"status": f"✓ Registered {len(viz_artifacts)} visualizations"})

    return {
        "new_artifact_ids": [final_artifact_id] + viz_artifacts
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
        final_artifacts = [a for a in state["new_artifact_ids"] if a.startswith("artifact_")]
        viz_artifacts = [a for a in state["new_artifact_ids"] if a.startswith("chart_")]
        if final_artifacts:
            summary_parts.append(f"✓ Generated final artifact: {final_artifacts[0]}")
        if viz_artifacts:
            summary_parts.append(f"✓ Generated {len(viz_artifacts)} visualization(s)")
    
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
