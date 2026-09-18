import os
import json
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

from src.config import settings

MODEL_NAME = "all-MiniLM-L6-v2"
CACHE_FILE = "embeddings_cache.npz"

_model: SentenceTransformer | None = None
_chunks: list[dict] | None = None
_embeddings: np.ndarray | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def _load_documents() -> list[dict]:
    kb_dir = Path(settings.knowledge_base_dir)
    docs = []
    for md_file in sorted(kb_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        chunks = _split_into_chunks(text, md_file.name)
        docs.extend(chunks)
    return docs


def _split_into_chunks(text: str, source: str) -> list[dict]:
    chunks = []
    current_lines = []
    current_header = ""

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            if current_lines:
                chunk_text = current_header + "\n" + "\n".join(current_lines).strip()
                if chunk_text.strip():
                    chunks.append({"text": chunk_text.strip(), "source": source})
            current_header = stripped
            current_lines = []
        elif stripped:
            current_lines.append(stripped)

    if current_lines:
        chunk_text = current_header + "\n" + "\n".join(current_lines).strip()
        if chunk_text.strip():
            chunks.append({"text": chunk_text.strip(), "source": source})

    return chunks


def _build_embeddings(chunks: list[dict]) -> np.ndarray:
    model = _get_model()
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return embeddings


def _cosine_similarity(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
    matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
    return matrix_norm @ query_norm


def _ensure_loaded() -> None:
    global _chunks, _embeddings

    if _chunks is not None and _embeddings is not None:
        return

    if os.path.exists(CACHE_FILE):
        data = np.load(CACHE_FILE, allow_pickle=True)
        _embeddings = data["embeddings"]
        _chunks = json.loads(str(data["chunks"]))
        return

    _chunks = _load_documents()
    _embeddings = _build_embeddings(_chunks)
    np.savez(
        CACHE_FILE,
        embeddings=_embeddings,
        chunks=np.array(json.dumps(_chunks)),
    )


def retrieve(query: str, top_k: int = 3) -> list[dict]:
    _ensure_loaded()
    model = _get_model()
    query_vec = model.encode(query, convert_to_numpy=True, show_progress_bar=False)
    scores = _cosine_similarity(query_vec, _embeddings)
    top_indices = np.argsort(scores)[::-1][:top_k]
    results = []
    for idx in top_indices:
        results.append({
            "text": _chunks[idx]["text"],
            "source": _chunks[idx]["source"],
            "score": float(scores[idx]),
        })
    return results


def build_cache() -> int:
    global _chunks, _embeddings
    _chunks = _load_documents()
    _embeddings = _build_embeddings(_chunks)
    np.savez(
        CACHE_FILE,
        embeddings=_embeddings,
        chunks=np.array(json.dumps(_chunks)),
    )
    return len(_chunks)
