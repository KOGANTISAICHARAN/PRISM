"""Text embedding abstraction for complaint clustering.

Preferred backend is sentence-transformers ``all-MiniLM-L6-v2`` (set
``EMBEDDING_BACKEND=sentence-transformers``). When that package/model is not
available the engine falls back to a character+word TF-IDF vector space, which
keeps semantic clustering functional in constrained environments.
"""

from __future__ import annotations

import numpy as np

from ..config import settings

_model = None
_backend_in_use = "tfidf"


def _load_sentence_transformer():
    global _model, _backend_in_use
    if _model is not None:
        return _model
    from sentence_transformers import SentenceTransformer  # type: ignore

    _model = SentenceTransformer(settings.embedding_model)
    _backend_in_use = "sentence-transformers"
    return _model


def backend_in_use() -> str:
    return _backend_in_use


def embed(texts: list[str]) -> np.ndarray:
    """Return L2-normalised embeddings, shape (n, dim)."""
    global _backend_in_use
    texts = [t if t and t.strip() else "unspecified food safety report" for t in texts]

    if settings.embedding_backend == "sentence-transformers":
        try:
            model = _load_sentence_transformer()
            vecs = np.asarray(model.encode(texts, normalize_embeddings=True), dtype=np.float32)
            return vecs
        except Exception:
            _backend_in_use = "tfidf (sentence-transformers unavailable)"

    from sklearn.feature_extraction.text import TfidfVectorizer

    n_features = 4096
    word = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, min_df=1)
    char = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
    try:
        w = word.fit_transform(texts).toarray()
    except ValueError:
        w = np.zeros((len(texts), 1))
    c = char.fit_transform(texts).toarray()
    mat = np.hstack([w, c])[:, :n_features].astype(np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return mat / norms


def cosine_matrix(vecs: np.ndarray) -> np.ndarray:
    return np.clip(vecs @ vecs.T, -1.0, 1.0)
