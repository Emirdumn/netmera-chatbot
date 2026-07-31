"""FastAPI uygulamasi.

Feature flag KAPALIYKEN hicbir uc nokta kayitli olmaz — uygulama ayaga
kalkar ama her istek 404 doner. Boylece "flag kapaliyken davranis hic
degismiyor" kabul kriteri saglanir.
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import WIDGET_ALLOWED_ORIGINS, WIDGET_API_ENABLED
from tools.rag_search_tool import warmup_retrieval

app = FastAPI(
    title="Netmera Destek Widget API",
    version="0.1.0",
    docs_url=None,      # dis dunyaya sema/dokuman acmiyoruz
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health() -> dict:
    """Konteyner healthcheck'i — flag kapaliyken de cevap verir."""
    return {"ok": True, "widget_enabled": WIDGET_API_ENABLED}


@app.on_event("startup")
def warmup_models() -> None:
    """Ilk widget mesajinin embedding model yukleme maliyetini azalt."""
    # Unit testlerde model yuklemek dakikalar surer; bilincli olarak atlanir.
    if os.environ.get("WIDGET_SKIP_WARMUP", "").lower() in ("1", "true", "yes"):
        return
    warmup_retrieval()


if WIDGET_API_ENABLED:
    # CORS: widget baska sitelere gomulecegi icin sart. Varsayilan olarak
    # HICBIR origin acik degil — WIDGET_ALLOWED_ORIGINS bilincli doldurulmali.
    # "*" kullanilmiyor: kimlik bilgisi tasiyan istekler icin zaten gecersiz
    # olurdu ve maliyet acisindan da acik kapi birakmak istemiyoruz.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=WIDGET_ALLOWED_ORIGINS,
        allow_credentials=False,   # token Authorization header'inda, cookie yok
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
        max_age=600,
    )

    from widget_api.routes import router

    app.include_router(router, prefix="/api/widget")
