"""本地 Embedding：sentence-transformers 全程本地推理，不上传任何聊天内容。"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

_MODELS: dict[str, SentenceTransformer] = {}


class LocalEmbedder:
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model_name = model_name

    def _model(self) -> SentenceTransformer:
        if self.model_name not in _MODELS:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise RuntimeError(
                    "缺少依赖 sentence-transformers：pip install sentence-transformers"
                ) from e
            _MODELS[self.model_name] = SentenceTransformer(self.model_name)
        return _MODELS[self.model_name]

    def embed(self, texts: list[str], batch_size: int = 64) -> np.ndarray:
        if not texts:
            return np.zeros((0, 512), dtype=np.float32)
        vecs = self._model().encode(
            texts, batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return np.asarray(vecs, dtype=np.float32)


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a(n,d) x b(m,d) → (n,m) 相似度矩阵（输入已归一化）。"""
    if a.size == 0 or b.size == 0:
        return np.zeros((len(a), len(b)), dtype=np.float32)
    return a @ b.T
