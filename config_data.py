import os
from dotenv import load_dotenv

load_dotenv()

# Paths
RAW_DOCS_DIR = "raw_docs"
SUMMARY_OUTPUT_PATH =  "combined_summary.txt"
QA_OUTPUT_CSV =  "qa_pairs.csv"
UPLOAD_TEMP_DIR = "uploads"

# Model / API config
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
MAX_SUMMARY_TOKENS = int(os.getenv("MAX_SUMMARY_TOKENS", "500"))
QA_PAIR_COUNT = int(os.getenv("QA_PAIR_COUNT", "100"))
