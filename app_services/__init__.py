"""Uygulama servis katmani.

UI (Streamlit) ve ileride widget_api (FastAPI) bu katman uzerinden konusur.
Graph calistirma, interrupt yonetimi ve DB persist mantigi BURADA durur —
sunum katmaninda degil. Boylece ayni davranis her iki on yuzde de birebir
ayni sekilde calisir.
"""
