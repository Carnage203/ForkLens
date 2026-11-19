"""Embed every recipe's doc_text with Gemini and write data/embeddings.npy + data/meta.json.

Run from the project root:  python -m scripts.build_embeddings
Needs GEMINI_API_KEY (in .env). Costs a few free-tier embedding calls.
"""
from __future__ import annotations

import io
import sys
import time

import numpy as np

from forklens.config import Settings
from forklens.exceptions import ForkLensError
from forklens.fileio.safe_io import SafeFile
from forklens.gemini import build_client
from forklens.rag.embedder import GeminiEmbedder
from forklens.rag.store import CorpusStore, LocalStore

BATCH = 20
PAUSE_S = 2.0


def main() -> int:
    """Build and save the embedding matrix; return a process exit code."""
    settings = Settings.load()
    if not settings.live_mode:
        print("GEMINI_API_KEY is missing. Put it in .env and run again.")
        return 1
    try:
        recipes = CorpusStore.parse_recipes(LocalStore(settings).fetch("recipes.jsonl"))
        embedder = GeminiEmbedder(build_client(settings), settings.embed_model, settings.embed_dim)
        texts = [r.doc_text for r in recipes]
        parts = []
        for start in range(0, len(texts), BATCH):
            parts.append(embedder.embed_documents(texts[start:start + BATCH]))
            print(f"embedded {min(start + BATCH, len(texts))}/{len(texts)}")
            time.sleep(PAUSE_S)
        matrix = np.vstack(parts).astype(np.float32)
        buffer = io.BytesIO()
        np.save(buffer, matrix)
        SafeFile(settings.data_dir / "embeddings.npy").write_bytes(buffer.getvalue())
        SafeFile(settings.data_dir / "meta.json").write_json(
            {"embed_model": settings.embed_model, "dim": settings.embed_dim, "count": len(recipes)})
    except ForkLensError as exc:
        print(f"Failed: {exc}")
        return 1
    print(f"Wrote embeddings {matrix.shape} to {settings.data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
