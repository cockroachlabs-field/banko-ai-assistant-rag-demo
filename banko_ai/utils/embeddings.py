"""One place to load the sentence-transformers embedding model.

Offline first: when the model is already in the local Hugging Face
cache, load it with local_files_only so no network request ever fires.
The airgap and wifi-off demos depend on this; hub checks otherwise
retry against huggingface.co and can take the whole app down. Only a
cold cache falls through to a normal (downloading) load.
"""

from __future__ import annotations

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def load_embedding_model(model_name: str = DEFAULT_EMBEDDING_MODEL):
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(model_name, local_files_only=True)
    except Exception:
        # Not cached yet (first ever run, or a new model name): this one
        # legitimately needs the network.
        return SentenceTransformer(model_name)
