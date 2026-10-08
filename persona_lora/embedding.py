"""本地 Embedding：sentence-transformers 全程本地推理，不上传任何聊天内容。"""
from __future__ import annotations

import importlib
from typing import Any

import numpy as np

_MODELS: dict[str, Any] = {}


class LocalEmbedder:
    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model_name = model_name

    def _model(self) -> Any:
        if self.model_name not in _MODELS:
            try:
                # 延迟动态加载（可选重依赖，缺失时给出友好报错）
                st_module = importlib.import_module("sentence_transformers")
            except ImportError as e:
                raise RuntimeError(
                    "缺少依赖 sentence-transformers：pip install sentence-transformers"
                ) from e
            _MODELS[self.model_name] = st_module.SentenceTransformer(self.model_name)
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
