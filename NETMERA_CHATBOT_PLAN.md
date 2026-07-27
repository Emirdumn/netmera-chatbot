# Netmera Chatbot — Lokal RAG Projesi (Ollama + Streamlit)

Netmera hakkında her soruyu cevaplayabilen, **tamamen lokal çalışan** (API token harcamayan) bir chatbot.

**Mimari:** RAG (Retrieval Augmented Generation)

```
netmera.com + user.netmera.com (dokümantasyon)
        │  scrape.py  (veri toplama)
        ▼
   data/ klasörü (düz metin + markdown)
        │  ingest.py  (parçalama + embedding)
        ▼
   ChromaDB (lokal vektör veritabanı)
        │  app.py  (Streamlit sohbet arayüzü)
        ▼
   Soru → ilgili parçalar bulunur → Ollama (lokal LLM) cevap üretir
```

**Neden bu tasarım ücretsiz:** Embedding modeli (`sentence-transformers`) ve LLM (Ollama)
tamamen kendi bilgisayarında çalışır. İnternete yalnızca 1. adımda (veri indirme) ihtiyaç var.

**Avantajımız:** Netmera'nın dokümantasyonu GitBook'ta ve her sayfayı doğrudan `.md`
(Markdown) olarak sunuyor; ayrıca `https://user.netmera.com/llms.txt` adresinde tüm
sayfaların listesi hazır. HTML ayrıştırmaya neredeyse hiç gerek kalmıyor.

---

## Adım 0 — Kurulum (bir kereye mahsus)

### 0.1 Ollama kur ve modeli indir

```bash
brew install ollama
```

(Homebrew yoksa https://ollama.com/download adresinden .dmg indir.)

Ollama servisini başlat ve modeli çek (~2 GB, bir kez indirilir):

```bash
brew services start ollama
ollama pull llama3.2:3b
```

> 16 GB+ RAM varsa daha kaliteli cevaplar için `ollama pull qwen2.5:7b` çekip
> `app.py` içindeki `LLM_MODEL` değişkenini değiştirebilirsin.

### 0.2 Proje klasörü ve Python ortamı

```bash
mkdir -p ~/netmera-bot && cd ~/netmera-bot
python3 -m venv venv
source venv/bin/activate
pip install requests beautifulsoup4 lxml sentence-transformers chromadb streamlit ollama
```

> İlk `pip install` birkaç dakika sürer (PyTorch indirir). Sonrasında her şey lokal.

---

## Adım 1 — Veri Toplama: `scrape.py`

Aşağıdaki dosyayı `~/netmera-bot/scrape.py` olarak kaydet:

```python
"""Netmera dokümantasyonunu ve web sitesini indirip data/ klasörüne kaydeder."""
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (NetmeraBot egitim projesi)"}
DATA_DIR = Path("data")
DELAY = 0.3  # siteyi yormamak icin istekler arasi bekleme (saniye)


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code == 200:
            return r.text
        print(f"  ! {r.status_code}: {url}")
    except requests.RequestException as e:
        print(f"  ! hata: {url} ({e})")
    return None


def safe_name(url):
    name = re.sub(r"https?://", "", url).strip("/")
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)[:180]


def save(folder, url, text):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (safe_name(url) + ".txt")
    path.write_text(f"URL: {url}\n\n{text}", encoding="utf-8")


def scrape_docs():
    """user.netmera.com — GitBook, tum sayfalar hazir Markdown olarak sunuluyor."""
    print("== Dokumantasyon (user.netmera.com) ==")
    llms = fetch("https://user.netmera.com/llms.txt")
    if not llms:
        print("llms.txt alinamadi!")
        return
    urls = sorted(set(re.findall(r"https://user\.netmera\.com/\S+\.md", llms)))
    print(f"{len(urls)} dokuman sayfasi bulundu")
    for i, url in enumerate(urls, 1):
        md = fetch(url)
        if md:
            save(DATA_DIR / "docs", url, md)
        if i % 20 == 0:
            print(f"  {i}/{len(urls)}")
        time.sleep(DELAY)


def scrape_site():
    """netmera.com — sitemap'lerdeki sayfalarin gorunur metnini cikarir."""
    print("== Web sitesi (netmera.com) ==")
    urls = set()
    for sm in ["https://netmera.com/page-sitemap.xml",
               "https://netmera.com/post-sitemap.xml"]:
        xml = fetch(sm)
        if xml:
            urls.update(re.findall(r"<loc>(https://netmera\.com/[^<]*)</loc>", xml))
    urls = sorted(urls)
    print(f"{len(urls)} site sayfasi bulundu")
    for i, url in enumerate(urls, 1):
        html = fetch(url)
        if html:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "footer", "header", "form"]):
                tag.decompose()
            text = re.sub(r"\n{3,}", "\n\n", soup.get_text(separator="\n").strip())
            if len(text) > 200:  # bos/anlamsiz sayfalari atla
                save(DATA_DIR / "site", url, text)
        if i % 20 == 0:
            print(f"  {i}/{len(urls)}")
        time.sleep(DELAY)


if __name__ == "__main__":
    scrape_docs()
    scrape_site()
    n = len(list(DATA_DIR.rglob("*.txt")))
    print(f"\nBitti: {n} sayfa data/ klasorune kaydedildi.")
```

Çalıştır:

```bash
python scrape.py
```

Beklenen sonuç: `data/docs/` altında ~180 dokümantasyon sayfası, `data/site/` altında
~100+ web sitesi sayfası (toplam birkaç dakika sürer).

---

## Adım 2 — İndeksleme: `ingest.py`

Aşağıdaki dosyayı `~/netmera-bot/ingest.py` olarak kaydet:

```python
"""data/ klasorundeki metinleri parcalara bolup ChromaDB'ye indeksler."""
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

# Turkce soru + Ingilizce dokuman uyumu icin cok dilli embedding modeli
EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
CHUNK_SIZE = 1200   # karakter
OVERLAP = 200


def chunk_text(text):
    chunks, start = [], 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - OVERLAP
    return chunks


def main():
    model = SentenceTransformer(EMBED_MODEL)  # ilk seferde ~500 MB indirir, sonra lokal
    client = chromadb.PersistentClient(path="chroma_db")
    try:
        client.delete_collection("netmera")  # yeniden calistirilirsa temiz baslasin
    except Exception:
        pass
    col = client.create_collection("netmera", metadata={"hnsw:space": "cosine"})

    docs, metas, ids = [], [], []
    files = sorted(Path("data").rglob("*.txt"))
    print(f"{len(files)} dosya indekslenecek")

    for f in files:
        raw = f.read_text(encoding="utf-8")
        first_line, _, body = raw.partition("\n\n")
        url = first_line.replace("URL: ", "").strip()
        for j, ch in enumerate(chunk_text(body)):
            docs.append(ch)
            metas.append({"url": url, "file": f.name})
            ids.append(f"{f.stem}-{j}")

    print(f"{len(docs)} parca, embedding hesaplaniyor (birkac dakika surebilir)...")
    embeddings = model.encode(docs, batch_size=64, show_progress_bar=True)

    for i in range(0, len(docs), 5000):  # chroma'ya parti parti yaz
        s = slice(i, i + 5000)
        col.add(documents=docs[s], embeddings=embeddings[s].tolist(),
                metadatas=metas[s], ids=ids[s])

    print(f"Bitti: {col.count()} parca chroma_db/ icine indekslendi.")


if __name__ == "__main__":
    main()
```

Çalıştır:

```bash
python ingest.py
```

---

## Adım 3 — Sohbet Arayüzü: `app.py`

Aşağıdaki dosyayı `~/netmera-bot/app.py` olarak kaydet:

```python
"""Netmera Chatbot — Streamlit arayuzu (lokal Ollama + ChromaDB RAG)."""
import chromadb
import ollama
import streamlit as st
from sentence_transformers import SentenceTransformer

EMBED_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
LLM_MODEL = "llama3.2:3b"   # daha guclu cevap icin: "qwen2.5:7b"
TOP_K = 5

SYSTEM_PROMPT = """Sen Netmera (omnichannel musteri etkilesim platformu) konusunda \
uzman bir asistansin. SADECE sana verilen baglam (dokumantasyon parcalari) icindeki \
bilgilere dayanarak cevap ver. Cevabi kullanicinin sorusuyla ayni dilde yaz \
(Turkce soruya Turkce, Ingilizce soruya Ingilizce). Baglamda cevap yoksa bunu \
durustce soyle, bilgi uydurma."""


@st.cache_resource
def load_resources():
    embedder = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path="chroma_db")
    return embedder, client.get_collection("netmera")


def retrieve(question, embedder, col):
    emb = embedder.encode([question])[0].tolist()
    res = col.query(query_embeddings=[emb], n_results=TOP_K)
    return list(zip(res["documents"][0], res["metadatas"][0]))


st.set_page_config(page_title="Netmera Chatbot", page_icon="💬")
st.title("💬 Netmera Chatbot")
st.caption("netmera.com + resmi dokumantasyon uzerinde egitilmis, tamamen lokal RAG botu")

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

    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    # onceki konusmayi da ver ki takip sorulari calissin (son 6 mesaj yeterli)
    history += st.session_state.messages[-7:-1]
    history.append({"role": "user",
                    "content": f"Baglam:\n{context}\n\nSoru: {question}"})

    with st.chat_message("assistant"):
        stream = ollama.chat(model=LLM_MODEL, messages=history, stream=True)
        answer = st.write_stream(part["message"]["content"] for part in stream)
        with st.expander("📚 Kullanilan kaynaklar"):
            for _, m in hits:
                st.markdown(f"- {m['url']}")

    st.session_state.messages.append({"role": "assistant", "content": answer})
```

Çalıştır:

```bash
streamlit run app.py
```

Tarayıcıda `http://localhost:8501` açılır — sohbet etmeye hazırsın. 🎉

---

## Hızlı Özet (tüm komutlar sırayla)

```bash
brew install ollama && brew services start ollama && ollama pull llama3.2:3b
```

```bash
mkdir -p ~/netmera-bot && cd ~/netmera-bot && python3 -m venv venv && source venv/bin/activate && pip install requests beautifulsoup4 lxml sentence-transformers chromadb streamlit ollama
```

Sonra `scrape.py`, `ingest.py`, `app.py` dosyalarını yukarıdan kopyalayıp oluştur ve:

```bash
python scrape.py && python ingest.py && streamlit run app.py
```

---

## Test Soruları (sunum için)

- "Netmera nedir, ne işe yarar?"
- "Rule-based segment nasıl oluşturulur?"
- "Mobile push notification göndermek için hangi adımları izlemeliyim?"
- "Geofence messaging nedir?"
- "What is a funnel and how do I create one?"
- "Webhook ayarları nereden yapılır?"

## Sorun Giderme

| Sorun | Çözüm |
|---|---|
| `ollama: connection refused` | `brew services start ollama` (veya ayrı terminalde `ollama serve`) |
| Cevaplar çok yavaş | Daha küçük model: `ollama pull llama3.2:1b` ve `app.py` içinde `LLM_MODEL` değiştir |
| Cevap kalitesi düşük | RAM yetiyorsa `qwen2.5:7b`; ayrıca `TOP_K` değerini 8'e çıkar |
| `get_collection` hatası | Önce `python ingest.py` çalıştırılmalı |
| Scrape sırasında bazı 404'ler | Normal — birkaç sayfa eksik olabilir, botu etkilemez |

## Opsiyonel: Ücretsiz Bulut API Yedeği (Groq)

Lokal model yetersiz kalırsa, Groq ücretsiz API key veriyor (kredi kartı istemez):
https://console.groq.com adresinden key al, `pip install groq` kur ve `app.py` içindeki
`ollama.chat(...)` çağrısını şununla değiştir:

```python
from groq import Groq
client = Groq(api_key="GROQ_API_KEYIN")
stream = client.chat.completions.create(
    model="llama-3.3-70b-versatile", messages=history, stream=True)
answer = st.write_stream(
    part.choices[0].delta.content or "" for part in stream)
```
