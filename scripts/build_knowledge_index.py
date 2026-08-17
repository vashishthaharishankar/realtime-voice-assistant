"""One-time script to index knowledge_base into Qdrant."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

warnings.filterwarnings("ignore")

KNOWLEDGE_DIR = ROOT / "knowledge_base"
MAX_PDF_PAGES = 80
MIN_CHUNK_CHARS = 40

SUPPORTED_TEXT = {".txt", ".md", ".csv"}
SUPPORTED_PDF = {".pdf"}


def chunk_text(text: str, size: int = 900, overlap: int = 120) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks


def read_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in SUPPORTED_TEXT:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix in SUPPORTED_PDF:
        try:
            from pypdf import PdfReader
        except ImportError:
            return ""
        try:
            reader = PdfReader(str(path), strict=False)
            page_count = len(reader.pages)
            if page_count > MAX_PDF_PAGES:
                print(f"  {path.name}: {page_count} pages, indexing first {MAX_PDF_PAGES}", flush=True)
            pages = []
            for page in reader.pages[:MAX_PDF_PAGES]:
                try:
                    pages.append(page.extract_text() or "")
                except Exception:
                    continue
            return "\n".join(pages)
        except Exception as exc:
            print(f"  skipping unreadable PDF {path.name}: {exc}", flush=True)
            return ""
    return ""


def collect_chunks() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    if not KNOWLEDGE_DIR.exists():
        return items
    files = [
        path
        for path in sorted(KNOWLEDGE_DIR.rglob("*"))
        if path.is_file() and path.suffix.lower() in SUPPORTED_TEXT | SUPPORTED_PDF
    ]
    print(f"Reading {len(files)} files from {KNOWLEDGE_DIR}...", flush=True)
    for path in files:
        print(f"  {path.name}", flush=True)
        text = read_file(path)
        chunks = [c for c in chunk_text(text) if len(c) >= MIN_CHUNK_CHARS]
        print(f"    -> {len(chunks)} chunks", flush=True)
        for idx, chunk in enumerate(chunks):
            items.append(
                {
                    "id": hashlib.sha256(f"{path.name}:{idx}:{chunk[:80]}".encode()).hexdigest()[:32],
                    "source": path.name,
                    "text": chunk,
                }
            )
    return items


def main() -> None:
    parser = argparse.ArgumentParser(description="Index Kotak Prime knowledge base into Qdrant")
    parser.add_argument("--recreate", action="store_true", help="Drop and recreate collection")
    args = parser.parse_args()

    from app.config import get_settings

    settings = get_settings()
    if not settings.qdrant_api_key or not settings.qdrant_url:
        raise SystemExit("Set QDRANT_URL and QDRANT_API_KEY in .env")

    chunks = collect_chunks()
    if not chunks:
        raise SystemExit(f"No indexable files found in {KNOWLEDGE_DIR}")

    openai = OpenAI(api_key=settings.openai_api_key)
    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=120,
    )

    sample = openai.embeddings.create(model=settings.embedding_model, input="dimension probe").data[0].embedding
    dim = len(sample)

    exists = client.collection_exists(settings.qdrant_collection)
    if args.recreate and exists:
        client.delete_collection(settings.qdrant_collection)
        exists = False

    if not exists:
        client.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
        )

    batch_size = 8
    total = len(chunks)
    print(f"Indexing {total} chunks into '{settings.qdrant_collection}'...")
    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        vectors = openai.embeddings.create(
            model=settings.embedding_model,
            input=[b["text"] for b in batch],
        ).data
        points = [
            qmodels.PointStruct(
                id=int(hashlib.sha256(b["id"].encode()).hexdigest()[:15], 16),
                vector=vectors[j].embedding,
                payload={"source": b["source"], "text": b["text"]},
            )
            for j, b in enumerate(batch)
        ]
        last_error = None
        for attempt in range(1, 4):
            try:
                client.upsert(
                    collection_name=settings.qdrant_collection,
                    points=points,
                    wait=False,
                )
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                print(f"  upsert retry {attempt}/3 after: {exc}")
        if last_error:
            raise last_error
        print(f"  {min(i + batch_size, total)}/{total}")

    print(f"Indexed {total} chunks into '{settings.qdrant_collection}'.")


if __name__ == "__main__":
    main()
