"""
Requirement 2, step 2 (part 1): pluggable semantic embedding backend for
Automated Field Mapping.

Nothing here knows about FA/MA/RR, GL, or any specific field name -- it
only turns a short text description of a field into a vector, and scores
two vectors with cosine similarity. Two backends, tried in this order:

  1. sentence-transformers, if the package is installed and its model
     can be loaded. This is a real semantic embedding model (knows that
     "COMPTE" and "Account" are related, not just string-similar) --
     the kind the requirement asks for. Configurable via the
     Unizero_EMBEDDING_MODEL env var (default: "all-MiniLM-L6-v2").
     Loading it needs network access the first time, to download model
     weights from Hugging Face.

  2. A dependency-free fallback: a deterministic hashed character
     n-gram vector (needs only numpy, already a project dependency).
     Being honest about its limits: this is NOT a real semantic
     embedding. It cannot know "COMPTE" means "Account" -- it has no
     notion of meaning at all. What it *does* do better than plain
     fuzzy-string matching is degrade gracefully when a real model
     isn't available (offline sandbox, no sentence-transformers
     installed) while still rewarding shared subword fragments across
     renamed fields (e.g. "TransactionDate" vs "Treasury Date" both
     containing "trans"/"date"-like 3-grams), and it combines with the
     value-similarity signal in auto_mapping.py so a field pair rarely
     has to rely on name evidence alone. Swap in a real model by
     installing sentence-transformers (`pip install sentence-transformers`)
     with network access -- no other code changes needed; this module
     picks it up automatically on next use.

Set Unizero_FORCE_HASH_EMBEDDER=1 to skip the sentence-transformers
attempt entirely and force the offline fallback -- used by the test
suite so results are deterministic and don't depend on network access
or a downloaded model.
"""

from __future__ import annotations

import hashlib
import logging
import os
import re

import numpy as np

logger = logging.getLogger("Unizero.field_mapping.embeddings")

_MODEL_NAME = os.environ.get("Unizero_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
_HASH_DIM = 256  # fallback vector width -- irrelevant once a real model loads
_TOKEN_RE = re.compile(r"[a-z0-9]+")


class _SentenceTransformerBackend:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # deferred import

        self._model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        return np.asarray(self._model.encode(list(texts), normalize_embeddings=True))


class _HashingBackend:
    """Deterministic, offline, dependency-free fallback -- see module docstring."""

    def _ngrams(self, text: str, n: int = 3) -> list[str]:
        tokens = _TOKEN_RE.findall(text.lower())
        joined = " ".join(tokens)
        if len(joined) < n:
            return [joined] if joined else []
        return [joined[i : i + n] for i in range(len(joined) - n + 1)]

    def embed(self, texts: list[str]) -> np.ndarray:
        vectors = np.zeros((len(texts), _HASH_DIM), dtype=np.float64)
        for row, text in enumerate(texts):
            for gram in self._ngrams(text):
                idx = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16) % _HASH_DIM
                vectors[row, idx] += 1.0
            norm = np.linalg.norm(vectors[row])
            if norm > 0:
                vectors[row] /= norm
        return vectors


_backend = None  # module-level cache, built once per process


def _get_backend():
    global _backend
    if _backend is not None:
        return _backend

    if os.environ.get("Unizero_FORCE_HASH_EMBEDDER"):
        logger.info("embeddings: Unizero_FORCE_HASH_EMBEDDER set, using offline hashing embedder")
        _backend = _HashingBackend()
        return _backend

    try:
        _backend = _SentenceTransformerBackend(_MODEL_NAME)
        logger.info("embeddings: using sentence-transformers model %r", _MODEL_NAME)
    except Exception as exc:  # noqa: BLE001 -- any failure (not installed, no
        # network to fetch weights, bad model name) must fall back, never
        # crash field mapping.
        logger.warning(
            "embeddings: sentence-transformers unavailable (%s) -- falling back to the "
            "offline hashing embedder. Semantic quality will be lower than a real model; "
            "install sentence-transformers with network access to fix.",
            exc,
        )
        _backend = _HashingBackend()
    return _backend


def embed_texts(texts: list[str]) -> np.ndarray:
    """Returns one row vector per input text, in order."""
    if not texts:
        return np.zeros((0, _HASH_DIM))
    return _get_backend().embed(texts)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.clip(np.dot(a, b) / denom, -1.0, 1.0))
