"""Proje genelinde kullanılan tüm sabitler tek yerde."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _required_env(name: str, *, min_length: int | None = None) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set in the environment or .env file.")
    if min_length is not None and len(value) < min_length:
        raise RuntimeError(f"{name} must be at least {min_length} characters long.")
    lowered = value.lower()
    if any(marker in lowered for marker in ("change-me", "changeme", "replace-me", "example")):
        raise RuntimeError(f"{name} must be changed from the placeholder value.")
    return value

# LLM
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "gemini")  # gemini | openrouter
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
LOG_TOOL_CALLS = os.environ.get("LOG_TOOL_CALLS", "true").lower() == "true"

# Tier'li model secimi — mimari sabit, model isimleri operasyonel ayar.
# Bos birakilirsa provider'in varsayilan modeline (GEMINI_MODEL /
# OPENROUTER_MODEL) duser; boylece davranis geriye uyumlu kalir.
_DEFAULT_CHAT_MODEL = OPENROUTER_MODEL if LLM_PROVIDER == "openrouter" else GEMINI_MODEL
LLM_CONTROL_MODEL = os.environ.get("LLM_CONTROL_MODEL", "").strip() or _DEFAULT_CHAT_MODEL
LLM_WORKER_MODEL = os.environ.get("LLM_WORKER_MODEL", "").strip() or _DEFAULT_CHAT_MODEL
LLM_BRAIN_MODEL = os.environ.get("LLM_BRAIN_MODEL", "").strip() or _DEFAULT_CHAT_MODEL
#: Tek LLM istegi icin timeout (saniye). 0 = kutuphane varsayilani.
LLM_REQUEST_TIMEOUT_SECONDS = float(os.environ.get("LLM_REQUEST_TIMEOUT_SECONDS", "60"))
#: brain cagrisi basarisiz olursa ayni istegi worker modeli ile bir kez dene.
LLM_BRAIN_FALLBACK_TO_WORKER = (
    os.environ.get("LLM_BRAIN_FALLBACK_TO_WORKER", "true").lower() == "true"
)
#: Her LLM cagrisinda tier/model/call_site/latency logla.
LLM_TELEMETRY_ENABLED = os.environ.get("LLM_TELEMETRY_ENABLED", "true").lower() == "true"

# Embedding
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

# RAG
TOP_K = 5
CONFIDENCE_THRESHOLD = 0.35
MAX_TOOL_ITERATIONS = 4  # FAZ 12 — ReAct dongusu: en fazla kac kez sorgu yeniden yazilip aranir

# Fast RAG gate — dokumanla guclu semantik eslesmede agir agent zincirine
# girmeden kaynakli cevap uretir; eslesme zayifsa once domain alakaliligini
# ayirir. Esikler env ile ayarlanabilir, varsayilanlar pilot veriye gore
# muhafazakar tutuldu.
FAST_RAG_ENABLED = os.environ.get("FAST_RAG_ENABLED", "true").lower() == "true"
FAST_RAG_DIRECT_THRESHOLD = float(os.environ.get("FAST_RAG_DIRECT_THRESHOLD", "0.50"))
FAST_RAG_REWRITE_THRESHOLD = float(
    os.environ.get("FAST_RAG_REWRITE_THRESHOLD", str(CONFIDENCE_THRESHOLD))
)

# Escalation
MAX_FAILED_ATTEMPTS = 2

# Cache (FAZ 15 — soru-cevap hizlandirma)
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
QA_CACHE_TTL_SECONDS = int(os.environ.get("QA_CACHE_TTL_SECONDS", str(3 * 24 * 3600)))  # 3 gun

# Widget API (FAZ 16) — dis sitelere gomulen widget'in konustugu HTTP katmani.
# VARSAYILAN KAPALI: flag kapaliyken tum uc noktalar 404 doner ve mevcut
# Streamlit davranisi hicbir sekilde degismez.
WIDGET_API_ENABLED = os.environ.get("WIDGET_API_ENABLED", "false").lower() == "true"
#: Virgulle ayrilmis origin listesi. Bos birakilirsa HICBIR dis origin
#: kabul edilmez (guvenli varsayilan — "*" ile acmak bilincli bir karar olmali).
WIDGET_ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get("WIDGET_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
#: IP basina dakikalik mesaj siniri — widget internete acik bir LLM ucu
#: oldugu icin maliyet/kotuye kullanim korumasi.
WIDGET_RATE_LIMIT_PER_MIN = int(os.environ.get("WIDGET_RATE_LIMIT_PER_MIN", "20"))
#: Anonim oturum token'larini imzalamak icin. Widget acikken ZORUNLU.
WIDGET_TOKEN_SECRET = (
    _required_env("WIDGET_TOKEN_SECRET", min_length=32) if WIDGET_API_ENABLED else ""
)

# Personel paneli girisi — nginx Basic Auth arkasindaki ikinci/ic kapi.
# Guvenlik nedeniyle varsayilan yoktur; canliya cikmadan .env icinde güçlü
# bir deger verilmezse uygulama acik ve erken bir hatayla durur.
STAFF_DEMO_PASSWORD = _required_env("STAFF_DEMO_PASSWORD", min_length=16)

# Yol sabitleri
DATA_DIR = BASE_DIR / "data"
USER_GUIDE_DIR = DATA_DIR / "user_guide"
DEV_GUIDE_DIR = DATA_DIR / "dev_guide"
WEBSITE_DIR = DATA_DIR / "website"
CHROMA_DIR = BASE_DIR / "chroma_db"
CHROMA_COLLECTION = "netmera"
# Calisma-zamani DB dosyalari kasitli olarak storage/data/ alt dizininde:
# docker-compose.yml bu klasoru AYRI bir volume olarak baglıyor, boylece
# storage/*.py KAYNAK KODU (repository.py, db.py) volume tarafindan
# gizlenmiyor/eskimiyor — storage/'un tamamini mount etmek bu dosyalarin
# her image guncellemesinde container icinde eski kalmasina yol aciyordu.
DB_PATH = BASE_DIR / "storage" / "data" / "helpdesk.db"
CHECKPOINT_DB_PATH = BASE_DIR / "storage" / "data" / "checkpoints.db"
