"""Proje genelinde kullanılan tüm sabitler tek yerde."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# LLM
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")  # gemini | openrouter
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
LOG_TOOL_CALLS = os.environ.get("LOG_TOOL_CALLS", "true").lower() == "true"

# Embedding
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# RAG
TOP_K = 5
CONFIDENCE_THRESHOLD = 0.35
MAX_TOOL_ITERATIONS = 4  # FAZ 12 — ReAct dongusu: en fazla kac kez sorgu yeniden yazilip aranir

# Escalation
MAX_FAILED_ATTEMPTS = 2

# Yol sabitleri
DATA_DIR = BASE_DIR / "data"
USER_GUIDE_DIR = DATA_DIR / "user_guide"
DEV_GUIDE_DIR = DATA_DIR / "dev_guide"
WEBSITE_DIR = DATA_DIR / "website"
CHROMA_DIR = BASE_DIR / "chroma_db"
CHROMA_COLLECTION = "netmera"
DB_PATH = BASE_DIR / "storage" / "helpdesk.db"
CHECKPOINT_DB_PATH = BASE_DIR / "storage" / "checkpoints.db"
