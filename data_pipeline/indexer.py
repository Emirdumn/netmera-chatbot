"""data/ altındaki tüm kaynakları okur, chunker ile böler, embed edip
tek 'netmera' koleksiyonuna yazar."""
import sys
from pathlib import Path

if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb
from sentence_transformers import SentenceTransformer

from config.settings import (
    CHROMA_COLLECTION,
    CHROMA_DIR,
    DEV_GUIDE_DIR,
    EMBED_MODEL,
    USER_GUIDE_DIR,
    WEBSITE_DIR,
)
from data_pipeline.chunker import chunk_markdown

SOURCE_DIRS = {
    "user_guide": USER_GUIDE_DIR,
    "dev_guide": DEV_GUIDE_DIR,
    "website": WEBSITE_DIR,
}


def _iter_source_files():
    for source, folder in SOURCE_DIRS.items():
        if not folder.exists():
            continue
        for f in sorted(folder.glob("*.txt")):
            yield source, f


def main():
    model = SentenceTransformer(EMBED_MODEL)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass
    col = client.create_collection(CHROMA_COLLECTION, metadata={"hnsw:space": "cosine"})

    docs, metas, ids = [], [], []
    n_files = 0
    for source, f in _iter_source_files():
        n_files += 1
        raw = f.read_text(encoding="utf-8")
        first_line, _, body = raw.partition("\n\n")
        url = first_line.replace("URL: ", "").strip()
        for j, chunk in enumerate(chunk_markdown(body, fallback_title=f.stem)):
            docs.append(chunk["text"])
            metas.append({
                "url": url,
                "source": source,
                "heading_path": chunk["heading_path"],
                "title": chunk["title"] or "",
            })
            ids.append(f"{source}-{f.stem}-{j}")

    print(f"{n_files} dosya, {len(docs)} parca indekslenecek")
    print("embedding hesaplaniyor (birkac dakika surebilir)...")
    embeddings = model.encode(docs, batch_size=64, show_progress_bar=True)

    for i in range(0, len(docs), 5000):
        s = slice(i, i + 5000)
        col.add(documents=docs[s], embeddings=embeddings[s].tolist(),
                metadatas=metas[s], ids=ids[s])

    print(f"Bitti: {col.count()} parca chroma_db/ icine indekslendi.")


if __name__ == "__main__":
    main()
