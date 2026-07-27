"""Netmera Chatbot — Streamlit arayuzu (Gemini + ChromaDB RAG).

LLM saglayicisi: GEMINI_API_KEY varsa Gemini, yoksa lokal Ollama'ya duser.
"""
import os

import chromadb
import streamlit as st
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
GEMINI_MODEL = "gemini-3.6-flash"
OLLAMA_MODEL = "qwen2.5:7b"   # sadece lokal fallback
TOP_K = 5

SYSTEM_PROMPT = """Sen Netmera (omnichannel musteri etkilesim platformu) konusunda \
uzman bir asistansin. SADECE sana verilen baglam (dokumantasyon parcalari) icindeki \
bilgilere dayanarak cevap ver. Cevabi kullanicinin sorusuyla ayni dilde yaz \
(Turkce soruya Turkce, Ingilizce soruya Ingilizce). Baglamda cevap yoksa bunu \
durustce soyle, bilgi uydurma."""


def get_api_key():
    """Once Streamlit secrets, sonra ortam degiskeni."""
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except FileNotFoundError:
        pass   # secrets.toml yoksa st.secrets patlar, sorun degil
    return os.environ.get("GEMINI_API_KEY")


@st.cache_resource
def load_resources():
    embedder = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path="chroma_db")
    return embedder, client.get_collection("netmera")


def retrieve(question, embedder, col):
    emb = embedder.encode([question])[0].tolist()
    res = col.query(query_embeddings=[emb], n_results=TOP_K)
    return list(zip(res["documents"][0], res["metadatas"][0]))


def stream_gemini(api_key, history, prompt):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    # Gemini rolleri: user / model
    contents = [
        types.Content(role="model" if m["role"] == "assistant" else "user",
                      parts=[types.Part(text=m["content"])])
        for m in history
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))

    stream = client.models.generate_content_stream(
        model=GEMINI_MODEL,
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def stream_ollama(history, prompt):
    import ollama

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages += history
    messages.append({"role": "user", "content": prompt})
    for part in ollama.chat(model=OLLAMA_MODEL, messages=messages, stream=True):
        yield part["message"]["content"]


st.set_page_config(page_title="Netmera Chatbot", page_icon="💬")
st.title("💬 Netmera Chatbot")
st.caption("netmera.com + resmi dokumantasyon uzerinde egitilmis RAG botu")

api_key = get_api_key()
embedder, col = load_resources()

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if question := st.chat_input("Netmera hakkinda bir soru sor..."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    hits = retrieve(question, embedder, col)
    context = "\n\n---\n\n".join(
        f"[Kaynak: {m['url']}]\n{doc}" for doc, m in hits)
    prompt = f"Baglam:\n{context}\n\nSoru: {question}"
    # onceki konusmayi da ver ki takip sorulari calissin (son 6 mesaj yeterli)
    history = st.session_state.messages[-7:-1]

    with st.chat_message("assistant"):
        if api_key:
            gen = stream_gemini(api_key, history, prompt)
        else:
            gen = stream_ollama(history, prompt)
        answer = st.write_stream(gen)
        with st.expander("📚 Kullanilan kaynaklar"):
            for _, m in hits:
                st.markdown(f"- {m['url']}")

    st.session_state.messages.append({"role": "assistant", "content": answer})
