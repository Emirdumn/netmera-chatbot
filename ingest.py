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
