# Agentic Data Processing System

A production-grade LangGraph-based data agent that intelligently processes datasets through multi-step planning, self-healing error recovery, and comprehensive artifact management.

## 🎯 Overview

This system transforms user requests into executable data workflows by:
- **Planning**: Breaking down complex requests into atomic steps
- **Routing**: Selecting the right tool for each step (pandas, visualization, profiling, analysis)
- **Executing**: Running generated code with schema validation
- **Recovering**: Auto-fixing errors through LLM-guided retries
- **Tracking**: Maintaining full lineage and reproducibility metadata

## 🏗️ Architecture

### Orchestrator-Worker Pattern with Error Recovery

```
┌─────────────────────────────────────────────────────────────────┐
│                         START                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │ Load Dataset    │ ── Load latest artifact
                    └────────┬────────┘    Extract schema
                             │
                    ┌────────▼────────┐
                    │ Plan Task       │ ── Break into steps
                    └────────┬────────┘    Classify task types
                             │
                    ┌────────▼────────┐
          ┌─────────┤ Route Tool      │ ── Choose: pandas/viz/
          │         └─────────────────┘    profiling/explain
          │
    ┌─────▼─────┐              ┌──────────────┐
    │ Explain   │              │ Reformulate  │ ── Schema-aware
    │ Only      │              │ Prompt       │    clarification
    └─────┬─────┘              └──────┬───────┘
          │                           │
          │                    ┌──────▼───────┐
          │                    │ Generate     │ ── LLM creates
          │                    │ Code         │    Python code
          │                    └──────┬───────┘
          │                           │
          │                    ┌──────▼───────┐
          │                    │ Execute      │ ── Run code
          │                    │ Code         │    safely
          │                    └──────┬───────┘
          │                           │
          │                    ┌──────▼───────┐
          │              ┌─────┤ Validate     │ ── Check schema
          │              │     │ Schema       │    changes
          │              │     └──────────────┘
          │              │            │
          │         [Error?]     [Success]
          │              │            │
          │      ┌───────▼──────┐     │
          │      │ Fix Code     │─────┘ (retry loop,
          │      │ (max 2x)     │        max 2 attempts)
          │      └──────────────┘
          │              │
          │         [Failed after
          │          retries]
          │              │
          │      ┌───────▼────────┐
          │      │ Error Summary  │
          │      └───────┬────────┘
          │              │
    ┌─────▼──────────────▼─────┐
    │ Mark Step Complete       │ ── Track progress
    └─────┬────────────────────┘    Reset for next
          │
    [More steps?] ──Yes──> Back to Route Tool
          │
         No
          │
    ┌─────▼─────────────┐
    │ Register          │ ── Save artifacts
    │ Artifacts         │    with metadata
    └─────┬─────────────┘
          │
    ┌─────▼─────────────┐
    │ Generate          │ ── Final summary
    │ Summary           │    + preview
    └─────┬─────────────┘
          │
    ┌─────▼─────────────┐
    │       END         │
    └───────────────────┘
```

### Key Components

#### 1. **State Management**
```python
class DatasetAgentState(TypedDict):
    # Planning
    plan: ExecutionPlan              # Structured task breakdown
    current_step_idx: int            # Current step being executed
    completed_steps: List[str]       # Completed step IDs
    
    # Execution
    tool_route: ToolRoute            # Selected tool for current step
    python_code_file: str            # Generated code location
    execution_error: Optional[str]   # Error tracking
    retry_count: int                 # Retry attempts
    
    # Schema Tracking
    schema_before: Dict              # Schema snapshot before step
    schema_after: Dict               # Schema snapshot after step
    schema_validation: SchemaChange  # Detected changes
    
    # Artifacts
    new_artifact_ids: List[str]      # All generated artifacts
    tool_history: List[Dict]         # Complete execution log
    intermediate_artifacts: List[str] # Charts, reports, etc.
```

#### 2. **Structured Planning**
```python
class ExecutionPlan(BaseModel):
    clarified_request: str           # User intent clarified
    columns_used: List[str]          # Schema references
    steps: List[TaskStep]            # Atomic execution steps
    assumptions: List[str]           # Documented assumptions

class TaskStep(BaseModel):
    step_id: str
    description: str
    task_type: Literal["transformation", "aggregation", 
                       "cleaning", "feature_engineering", 
                       "visualization", "analysis"]
    requires_code: bool
    requires_visualization: bool
    depends_on: List[str]            # Step dependencies
```

#### 3. **Error Recovery**
- **Auto-fix loop**: Failed code is sent back to LLM with error context
- **Max retries**: 2 attempts per step to prevent infinite loops
- **Error context**: Full traceback + schema info for intelligent fixes
- **Graceful degradation**: Informative error summary if recovery fails

#### 4. **Schema Protection**
```python
class SchemaChange(BaseModel):
    columns_added: List[str]
    columns_removed: List[str]
    dtypes_changed: Dict[str, str]
    row_count_change: int
    is_intentional: bool             # LLM validates intent
```

## 📊 Example Workflows

### Example 1: Data Cleaning + Aggregation

**Input:**
```python
"Remove rows where name or sales is missing, then group by region 
and product to calculate total sales, average sales, and count."
```

**Execution Plan Generated:**
```json
{
  "clarified_request": "Remove rows where 'name' or 'sales' is missing, 
                        then group by 'region' and 'product' to calculate 
                        total sales, average sales, and count.",
  "columns_used": ["name", "sales", "region", "product"],
  "steps": [
    {
      "step_id": "1",
      "description": "Filter out rows where 'name' or 'sales' is missing",
      "task_type": "cleaning",
      "requires_code": true,
      "requires_visualization": false,
      "depends_on": []
    },
    {
      "step_id": "2",
      "description": "Group the filtered data by 'region' and 'product'",
      "task_type": "aggregation",
      "requires_code": true,
      "requires_visualization": false,
      "depends_on": ["1"]
    },
    {
      "step_id": "3",
      "description": "Calculate total sales, average sales, and count",
      "task_type": "aggregation",
      "requires_code": true,
      "requires_visualization": false,
      "depends_on": ["2"]
    }
  ],
  "assumptions": [
    "The 'sales' column contains numeric values suitable for aggregation",
    "The 'name' column is considered missing if it is null"
  ]
}
```

**Generated Code (Step 1):**
```python
# Filter rows where 'name' or 'sales' is missing
df = df.dropna(subset=['name', 'sales'])
```

**Generated Code (Step 2 + 3):**
```python
# Group by region and product, calculate aggregations
df = df.groupby(['region', 'product']).agg(
    total_sales=('sales', 'sum'),
    average_sales=('sales', 'mean'),
    count_entries=('sales', 'count')
).reset_index()
```

**Output:**
```
✓ Task completed successfully
✓ Executed 3 steps
✓ Final dataset: 7 rows × 8 columns
✓ Generated 1 artifacts
  - Added columns: average_sales, total_sales, count_entries

Preview:
┌────────┬─────────┬─────────────┬───────────────┬───────────────┐
│ region │ product │ total_sales │ average_sales │ count_entries │
├────────┼─────────┼─────────────┼───────────────┼───────────────┤
│ East   │ A       │ 300.0       │ 300.0         │ 1             │
│ East   │ B       │ 450.0       │ 450.0         │ 1             │
│ North  │ A       │ 140.0       │ 140.0         │ 1             │
│ North  │ B       │ 220.0       │ 110.0         │ 2             │
│ South  │ C       │ 290.0       │ 145.0         │ 2             │
│ West   │ A       │ 240.0       │ 120.0         │ 2             │
│ West   │ C       │ 210.0       │ 210.0         │ 1             │
└────────┴─────────┴─────────────┴───────────────┴───────────────┘
```

### Example 2: Feature Engineering + Visualization

**Input:**
```python
"Create a new column 'sales_category' that labels sales as 'Low' (<100), 
'Medium' (100-200), or 'High' (>200), then create a bar chart showing 
the count of each category by region."
```

**Expected Plan:**
```json
{
  "steps": [
    {
      "step_id": "1",
      "description": "Create 'sales_category' column with Low/Medium/High labels",
      "task_type": "feature_engineering",
      "requires_code": true,
      "requires_visualization": false
    },
    {
      "step_id": "2",
      "description": "Create bar chart of sales categories by region",
      "task_type": "visualization",
      "requires_code": true,
      "requires_visualization": true
    }
  ]
}
```

**Generated Code (Step 1):**
```python
import numpy as np

def categorize_sales(value):
    if pd.isna(value):
        return None
    elif value < 100:
        return 'Low'
    elif value <= 200:
        return 'Medium'
    else:
        return 'High'

df['sales_category'] = df['sales'].apply(categorize_sales)
```

**Generated Code (Step 2):**
```python
import matplotlib.pyplot as plt
import seaborn as sns

# Count sales categories by region
category_counts = df.groupby(['region', 'sales_category']).size().unstack(fill_value=0)

# Create bar chart
fig, ax = plt.subplots(figsize=(10, 6))
category_counts.plot(kind='bar', ax=ax, color=['#ff6b6b', '#ffd93d', '#6bcf7f'])
ax.set_title('Sales Category Distribution by Region', fontsize=14, fontweight='bold')
ax.set_xlabel('Region', fontsize=12)
ax.set_ylabel('Count', fontsize=12)
ax.legend(title='Sales Category', loc='upper right')
plt.xticks(rotation=45)
plt.tight_layout()
```

**Output:**
```
✓ Task completed successfully
✓ Executed 2 steps
✓ Final dataset: 20 rows × 6 columns
✓ Generated 2 artifacts (1 dataset + 1 chart)
  - Added columns: sales_category
  - Chart saved: chart_a4f5b2c1.png
```

### Example 3: Error Recovery in Action

**Input:**
```python
"Calculate the correlation between sales and date"
```

**Initial Attempt (Fails):**
```python
# Generated code tries to correlate string dates
correlation = df['sales'].corr(df['date'])
```

**Error:**
```
TypeError: cannot perform correlation on string dtype
```

**Auto-Fix (Retry 1):**
```python
# LLM recognizes date needs conversion
df['date'] = pd.to_datetime(df['date'])
df['date_numeric'] = (df['date'] - df['date'].min()).dt.days
correlation = df['sales'].corr(df['date_numeric'])
print(f"Correlation: {correlation}")
```

**Output:**
```
✓ Step complete after 1 retry
✓ Task completed successfully
✓ Code auto-fixed: converted date strings to numeric values
```

### Example 4: Explanation-Only Task

**Input:**
```python
"Explain what insights we can derive from the sales data by region"
```

**Tool Routing Decision:**
```json
{
  "primary_tool": "explanation",
  "needs_execution": false,
  "rationale": "This is an analytical question requiring interpretation, 
               not data transformation"
}
```

**Output:**
```
Step 1: Analysis of regional sales patterns

From the current dataset with 20 rows across 4 regions (East, West, North, South):

Key Insights:
1. Regional Performance: We can identify which regions generate the most 
   revenue by summing sales by region. This reveals geographic strengths 
   and opportunities.

2. Regional Consistency: Standard deviation of sales within each region 
   shows market stability vs. volatility.

3. Product-Region Mix: Cross-tabulating region with product types reveals 
   which products perform best in which markets, informing targeted 
   marketing strategies.

4. Missing Data Patterns: Analyzing null values in sales by region could 
   indicate data collection issues or operational gaps in specific areas.

Recommended next steps:
- Group by region and calculate sum, mean, std of sales
- Create regional comparison visualizations
- Examine outliers for strategic opportunities
```

## 🚀 Usage

### Basic Usage

```python
from langgraph_data_agent_improved import build_dataset_agent_graph, DatasetAgentState
import asyncio

async def process_data():
    agent = build_dataset_agent_graph()
    
    state: DatasetAgentState = {
        "dataset_id": "ds_12345abc",
        "original_prompt": "Your data processing request here",
        "thread_id": "thread_001",
    }
    
    async for mode, chunk in agent.astream(
        state,
        stream_mode=["updates", "custom"],
        config={"configurable": {"thread_id": state["thread_id"]}}
    ):
        if mode == "custom":
            print(f"[STATUS] {chunk}")
        elif mode == "updates":
            for node_name, output in chunk.items():
                print(f"[NODE: {node_name}] {output}")

asyncio.run(process_data())
```

### Dataset Setup

```python
from langgraph_data_agent_improved import (
    generate_id, save_dataframe, save_json, 
    DATASET_DIR, ARTIFACT_DIR
)
import pandas as pd
from datetime import datetime, timezone

# 1. Create dataset
dataset_id = generate_id("ds")
df = pd.read_csv("your_data.csv")

# 2. Save original
original_path = os.path.join(DATASET_DIR, f"{dataset_id}_original.csv")
df.to_csv(original_path, index=False)

# 3. Create dataset metadata
dataset_meta = {
    "id": dataset_id,
    "name": "My Dataset",
    "original_file": original_path,
    "schema": list(df.columns),
    "created_at": datetime.now(timezone.utc).isoformat(),
    "owner_id": "user_123",
    "artifacts": [],
}
save_json(dataset_meta, os.path.join(DATASET_DIR, f"{dataset_id}.json"))

# 4. Create base artifact
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

# 5. Link artifact to dataset
dataset_meta["artifacts"].append(base_artifact_id)
save_json(dataset_meta, os.path.join(DATASET_DIR, f"{dataset_id}.json"))
```

## 📁 Storage Structure

```
data_agent_storage/
├── datasets/
│   ├── ds_12345abc.json              # Dataset metadata
│   └── ds_12345abc_original.csv      # Original data
│
├── artifacts/
│   ├── artifact_abc123.csv           # Base artifact
│   ├── artifact_abc123.json          # Base metadata
│   ├── artifact_def456.csv           # Derived artifact
│   └── artifact_def456.json          # Derived metadata (with lineage)
│
├── python_code/
│   ├── artifact_abc123_1.py          # Step 1 code
│   ├── artifact_abc123_2.py          # Step 2 code
│   └── artifact_abc123_2_retry1.py   # Retry code (if needed)
│
├── images/
│   ├── chart_xyz789.png              # Generated visualizations
│   └── chart_xyz789.json             # Chart metadata
│
└── reports/
    └── report_summary.json           # Analysis reports
```

## 🔍 Artifact Metadata Example

```json
{
  "id": "artifact_41dd3154",
  "dataset_id": "ds_e356613c",
  "thread_id": "thread_123",
  "type": "derived_dataset",
  "created_at": "2026-02-12T10:30:45.123456Z",
  "lineage": ["artifact_e356613c"],
  "transformation_type": "multi_step_plan",
  "plan_summary": "Remove rows where 'name' or 'sales' is missing, then group by 'region' and 'product' to calculate total sales, average sales, and count.",
  "steps_executed": ["1", "2", "3"],
  "tool_history": [
    {
      "step_id": "1",
      "tool": "pandas",
      "code_file": "/path/to/artifact_e356613c_1.py",
      "code_hash": "55d08bf4add63405",
      "timestamp": "2026-02-12T10:30:46.789Z"
    },
    {
      "step_id": "2",
      "tool": "pandas",
      "code_file": "/path/to/artifact_e356613c_2.py",
      "code_hash": "5d06d1394087c041",
      "timestamp": "2026-02-12T10:30:48.234Z"
    },
    {
      "step_id": "3",
      "tool": "pandas",
      "code_file": "/path/to/artifact_e356613c_3.py",
      "code_hash": "af178c451cf50db9",
      "timestamp": "2026-02-12T10:30:49.678Z"
    }
  ],
  "schema": {
    "columns": ["region", "product", "total_sales", "average_sales", "count_entries"],
    "dtypes": {
      "region": "object",
      "product": "object",
      "total_sales": "float64",
      "average_sales": "float64",
      "count_entries": "int64"
    },
    "row_count": 7,
    "null_counts": {
      "region": 0,
      "product": 0,
      "total_sales": 0,
      "average_sales": 0,
      "count_entries": 0
    }
  },
  "metadata": {
    "rows": 7,
    "columns": 5,
    "plan_steps": 3
  }
}
```

## ⚙️ Configuration

### Environment Variables

```bash
# .env file
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key
```

### Storage Directories

Configure storage paths at the top of the script:

```python
BASE_STORAGE_DIR = "data_agent_storage"
DATASET_DIR = os.path.join(BASE_STORAGE_DIR, "datasets")
ARTIFACT_DIR = os.path.join(BASE_STORAGE_DIR, "artifacts")
CODE_DIR = os.path.join(BASE_STORAGE_DIR, "python_code")
IMAGE_DIR = os.path.join(BASE_STORAGE_DIR, "images")
REPORT_DIR = os.path.join(BASE_STORAGE_DIR, "reports")
```

### LLM Configuration

```python
model = init_chat_model(
    "azure_openai:gpt-4.1",
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    temperature=0,  # Deterministic for code generation
)
```

## 🛡️ Safety Features

### 1. **Schema Protection**
- Tracks all column additions/removals
- Validates dtype changes
- Monitors row count changes
- LLM confirms intentionality

### 2. **Code Sandboxing**
- Executes in isolated namespace
- No file system access from generated code
- No network calls
- Limited to pandas/matplotlib operations

### 3. **Error Boundaries**
- Try-catch around all code execution
- Maximum retry limits
- Graceful degradation
- Comprehensive error logging

### 4. **Reproducibility**
- Code hash for each execution
- Complete lineage tracking
- Timestamped operations
- Version-controlled artifacts

## 🎓 Design Patterns Used

1. **Orchestrator-Worker**: Central planner delegates to specialized workers
2. **Evaluator-Optimizer**: Validate → Fix → Retry loop
3. **Routing**: Conditional branching based on task classification
4. **State Machine**: Explicit state transitions with checkpointing

## 📈 Performance Characteristics

- **Planning Overhead**: ~2-3 seconds for complex multi-step tasks
- **Code Generation**: ~1-2 seconds per step
- **Execution**: Depends on data size and operation
- **Error Recovery**: Adds ~3-5 seconds per retry
- **Total Time**: Typically 10-30 seconds for 3-5 step workflows

## 🔮 Future Enhancements

- [ ] Parallel step execution for independent tasks
- [ ] Advanced profiling tools (data quality, distributions)
- [ ] SQL query generation for database backends
- [ ] Interactive visualization dashboards
- [ ] Collaborative filtering for multi-user scenarios
- [ ] Model training and prediction pipelines
- [ ] Automated A/B testing for transformations
- [ ] Natural language query interface for results

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.

## 📧 Support

For issues and questions, please open a GitHub issue or contact the maintainers.

---

**Built with**: LangGraph, LangChain, Pandas, Matplotlib, Pydantic