# backend/models.py
from typing import TypedDict, Optional, Dict, Any, List, Literal, Annotated
from pydantic import BaseModel, Field
import operator

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
