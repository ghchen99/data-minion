# backend/config.py
import os
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model

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
