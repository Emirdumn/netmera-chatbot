# 💬 Netmera Chatbot

netmera.com ve resmi dokumantasyon uzerinde calisan RAG chatbot.

- **Retrieval:** ChromaDB + `paraphrase-multilingual-MiniLM-L12-v2` embeddings (3812 chunk)
- **LLM:** Google Gemini (`gemini-3.6-flash`)
- **Arayuz:** Streamlit

## Ayar

`GEMINI_API_KEY` gerekli:

- **Streamlit Cloud:** App settings → Secrets → `GEMINI_API_KEY = "..."`
- **Lokal:** `.streamlit/secrets.toml` icine `GEMINI_API_KEY = "..."`
  (veya `export GEMINI_API_KEY=...`)

Key yoksa uygulama lokal Ollama'ya (`qwen2.5:7b`) duser.

## Calistirma

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Veri hatti

```bash
python scrape.py   # siteyi tarar -> data/
python ingest.py   # embed edip chroma_db/ olusturur
```
