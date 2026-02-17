# backend/utils.py
import os
import uuid
import hashlib
import json
import pandas as pd
from typing import Dict, Any
from config import ARTIFACT_DIR, CODE_DIR
from models import SchemaChange

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
