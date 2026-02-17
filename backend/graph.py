from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from models import DatasetAgentState
from nodes import (
    load_latest_dataset, plan_task, route_tool, should_execute_code,
    reformulate_prompt, generate_python_code, execute_python_code,
    validate_schema_change, check_execution_success, fix_code_with_error,
    explain_only_node, mark_step_complete, check_more_steps,
    register_artifacts, generate_summary, error_summary_node
)

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
