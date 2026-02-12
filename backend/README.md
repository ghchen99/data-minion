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
          │                    │ Code         │    Create intermediate
          │                    └──────┬───────┘    artifact (no overwrite)
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
    │ Register          │ ── Save final artifact
    │ Artifacts         │    with full lineage
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
    artifact_id: str                 # Current working artifact (updated each step)
    new_artifact_ids: List[str]      # All generated artifacts
    tool_history: List[Dict]         # Complete execution log
    intermediate_artifacts: List[str] # Intermediate data + charts
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

#### 5. **Intermediate Artifact Management** ⭐ NEW
- **No Overwriting**: Each transformation step creates a NEW intermediate artifact
- **Chain of Custody**: State's `artifact_id` is updated to point to the latest intermediate artifact
- **Full Lineage**: All intermediate artifacts are tracked in `intermediate_artifacts` list
- **Final Registration**: The last intermediate artifact is copied to create the final registered artifact

**Artifact Flow Example:**
```
base_artifact (20 rows, 5 cols)
    ↓ Step 1: Clean nulls
intermediate_abc123 (17 rows, 5 cols)  ← Created, not overwritten
    ↓ Step 2: Add category column
intermediate_def456 (17 rows, 6 cols)  ← Created, not overwritten
    ↓ Step 3: Aggregate
intermediate_ghi789 (9 rows, 3 cols)   ← Created, not overwritten
    ↓ Register
final_artifact (9 rows, 3 cols)        ← Copy with full metadata

Result: base_artifact remains unchanged at 20 rows!
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

**Intermediate Artifact Created:** `intermediate_a1b2c3d4` (17 rows, 5 columns)

**Generated Code (Step 2 + 3):**
```python
# Group by region and product, calculate aggregations
df = df.groupby(['region', 'product']).agg(
    total_sales=('sales', 'sum'),
    average_sales=('sales', 'mean'),
    count_entries=('sales', 'count')
).reset_index()
```

**Intermediate Artifacts Created:** 
- `intermediate_e5f6g7h8` (after grouping)
- `intermediate_i9j0k1l2` (after aggregation)

**Output:**
```
✓ Task completed successfully
✓ Executed 3 steps
✓ Final dataset: 7 rows × 5 columns
✓ Generated final artifact: artifact_41dd3154
  - Added columns: total_sales, average_sales, count_entries
  - Row count change: -13 (from 20 to 7)

Preview:
[
  {
    "region": "East",
    "product": "A",
    "total_sales": 300.0,
    "average_sales": 300.0,
    "count_entries": 1
  },
  {
    "region": "East",
    "product": "B",
    "total_sales": 450.0,
    "average_sales": 450.0,
    "count_entries": 1
  },
  {
    "region": "North",
    "product": "A",
    "total_sales": 140.0,
    "average_sales": 140.0,
    "count_entries": 1
  }
]
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
      "description": "Handle missing values in 'sales' column",
      "task_type": "cleaning",
      "requires_code": true,
      "requires_visualization": false
    },
    {
      "step_id": "2",
      "description": "Create 'sales_category' column with Low/Medium/High labels",
      "task_type": "feature_engineering",
      "requires_code": true,
      "requires_visualization": false
    },
    {
      "step_id": "3",
      "description": "Aggregate counts by region and sales_category",
      "task_type": "aggregation",
      "requires_code": true,
      "requires_visualization": false
    },
    {
      "step_id": "4",
      "description": "Create bar chart of sales categories by region",
      "task_type": "visualization",
      "requires_code": true,
      "requires_visualization": true
    }
  ]
}
```

**Intermediate Artifacts Created:**
- `intermediate_abc123` (after cleaning nulls)
- `intermediate_def456` (after adding sales_category column)
- `intermediate_ghi789` (after aggregation - 9 rows)
- `chart_xyz789` (visualization, no data change)

**Generated Code (Step 2):**
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

**Generated Code (Step 4):**
```python
import matplotlib.pyplot as plt
import seaborn as sns

sns.set_theme(style="whitegrid")

# Create grouped bar chart
fig, ax = plt.subplots(figsize=(10, 6))
pivot_data = df.pivot(index='region', columns='sales_category', values='count')
pivot_data.plot(kind='bar', ax=ax, color=['#ff6b6b', '#ffd93d', '#6bcf7f'])

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
✓ Executed 4 steps
✓ Final dataset: 9 rows × 3 columns
✓ Generated final artifact: artifact_ef3861b5
✓ Generated 1 visualization(s)
  - Added columns: sales_category
  - Chart saved: chart_6259eb2b.png

Preview:
[
  {
    "region": "East",
    "sales_category": "High",
    "count": 3
  },
  {
    "region": "East",
    "sales_category": "Low",
    "count": 1
  },
  {
    "region": "East",
    "sales_category": "Medium",
    "count": 1
  }
]
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
✓ Created intermediate artifact: intermediate_m4n5o6p7
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
│   └── ds_12345abc_original.csv      # Original data (never modified)
│
├── artifacts/
│   ├── artifact_abc123.csv           # Base artifact (never modified)
│   ├── artifact_abc123.json          # Base metadata
│   ├── intermediate_def456.csv       # Step 1 output
│   ├── intermediate_def456.json      # Step 1 metadata
│   ├── intermediate_ghi789.csv       # Step 2 output
│   ├── intermediate_ghi789.json      # Step 2 metadata
│   ├── artifact_final123.csv         # Final registered artifact
│   └── artifact_final123.json        # Final metadata (with lineage)
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
  "id": "artifact_ef3861b5",
  "dataset_id": "ds_6d32f7ab",
  "thread_id": "thread_123",
  "type": "derived_dataset",
  "created_at": "2026-02-12T22:20:38.164974+00:00",
  "lineage": [
    "intermediate_a1b2c3d4",
    "intermediate_e5f6g7h8", 
    "intermediate_i9j0k1l2"
  ],
  "transformation_type": "multi_step_plan",
  "plan_summary": "Create a new column 'sales_category' based on the 'sales' column values, then generate a bar chart showing the count of each 'sales_category' by 'region'.",
  "steps_executed": ["1", "2", "3", "4"],
  "tool_history": [
    {
      "step_id": "1",
      "tool": "pandas",
      "code_file": "data_agent_storage\\python_code\\artifact_d7946812_1.py",
      "code_hash": "dea0b0732c10eb06",
      "timestamp": "2026-02-12T22:19:24.889107+00:00"
    },
    {
      "step_id": "2",
      "tool": "pandas",
      "code_file": "data_agent_storage\\python_code\\artifact_d7946812_2.py",
      "code_hash": "6773c1de94b7b09c",
      "timestamp": "2026-02-12T22:19:48.273938+00:00"
    },
    {
      "step_id": "3",
      "tool": "pandas",
      "code_file": "data_agent_storage\\python_code\\artifact_d7946812_3.py",
      "code_hash": "b47061696d8fe7a3",
      "timestamp": "2026-02-12T22:20:08.280070+00:00"
    },
    {
      "step_id": "4",
      "tool": "visualization",
      "code_file": "data_agent_storage\\python_code\\artifact_d7946812_4.py",
      "code_hash": "68a0c1c2aa7ceab1",
      "timestamp": "2026-02-12T22:20:37.945937+00:00"
    }
  ],
  "schema": {
    "columns": ["region", "sales_category", "count"],
    "dtypes": {
      "region": "str",
      "sales_category": "str",
      "count": "int64"
    },
    "row_count": 9,
    "null_counts": {
      "region": 0,
      "sales_category": 0,
      "count": 0
    }
  },
  "metadata": {
    "rows": 9,
    "columns": 3,
    "plan_steps": 4
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
    "azure_openai:gpt-4o",
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

### 2. **Artifact Immutability** ⭐ NEW
- **Original artifacts never modified**: Base datasets remain pristine
- **Copy-on-write**: Each transformation creates a new intermediate artifact
- **State tracking**: `artifact_id` in state always points to latest version
- **Full lineage**: Complete chain from base → intermediate → final

### 3. **Code Sandboxing**
- Executes in isolated namespace
- No file system access from generated code
- No network calls
- Limited to pandas/matplotlib operations

### 4. **Error Boundaries**
- Try-catch around all code execution
- Maximum retry limits (2 per step)
- Graceful degradation
- Comprehensive error logging

### 5. **Reproducibility**
- Code hash for each execution
- Complete lineage tracking
- Timestamped operations
- Version-controlled artifacts

## 🎓 Design Patterns Used

1. **Orchestrator-Worker**: Central planner delegates to specialized workers
2. **Evaluator-Optimizer**: Validate → Fix → Retry loop
3. **Routing**: Conditional branching based on task classification
4. **State Machine**: Explicit state transitions with checkpointing
5. **Copy-on-Write**: Immutable artifacts with versioned transformations

## 📈 Performance Characteristics

- **Planning Overhead**: ~2-3 seconds for complex multi-step tasks
- **Code Generation**: ~1-2 seconds per step
- **Execution**: Depends on data size and operation
- **Artifact I/O**: ~0.1-0.5 seconds per intermediate save (overhead justified by safety)
- **Error Recovery**: Adds ~3-5 seconds per retry
- **Total Time**: Typically 15-40 seconds for 3-5 step workflows

## 🐛 Bug Fixes

### v1.1.0 - Intermediate Artifact Fix
**Issue**: Original artifacts were being overwritten by each transformation step, resulting in loss of intermediate states and making the base artifact contain final transformed data.

**Root Cause**: `execute_python_code()` was saving transformed DataFrames back to the same `artifact_id` that was loaded as input.

**Fix**: 
- Each data transformation step now creates a NEW `intermediate_xxxxx` artifact
- State's `artifact_id` is updated to point to the new intermediate artifact
- All intermediates are tracked in `intermediate_artifacts` list
- Final `register_artifacts` step creates the registered artifact with full lineage
- Base artifacts remain unchanged, preserving data integrity

**Impact**: Ensures data provenance, enables step-by-step debugging, and maintains artifact immutability.

## 🔮 Future Enhancements

- [ ] Parallel step execution for independent tasks
- [ ] Advanced profiling tools (data quality, distributions)
- [ ] SQL query generation for database backends
- [ ] Interactive visualization dashboards
- [ ] Collaborative filtering for multi-user scenarios
- [ ] Model training and prediction pipelines
- [ ] Automated A/B testing for transformations
- [ ] Natural language query interface for results
- [ ] Checkpoint/resume for long-running workflows
- [ ] Artifact garbage collection (auto-cleanup of old intermediates)

## 📝 License

MIT License - see LICENSE file for details

## 🤝 Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.

## 📧 Support

For issues and questions, please open a GitHub issue or contact the maintainers.

---

**Built with**: LangGraph, LangChain, Pandas, Matplotlib, Seaborn, Pydantic

**Version**: 1.1.0 (Fixed intermediate artifact handling)