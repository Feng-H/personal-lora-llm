"""样本存储：统一 JSONL 文件（data/dataset/samples.jsonl），全链路唯一数据源。"""
from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

SOURCES = ("questionnaire", "agent_chat", "im_import")
STATUSES = ("approved", "pending", "rejected")


def new_sample(
    source: str,
    scene: str,
    messages: list[dict],
    flags: list[str] | None = None,
    status: str = "approved",
    meta: dict | None = None,
) -> dict:
    assert source in SOURCES, f"未知来源: {source}"
    assert status in STATUSES, f"未知状态: {status}"
    return {
        "id": uuid.uuid4().hex[:12],
        "source": source,
        "scene": scene,
        "status": status,
        "flags": flags or [],
        "messages": messages,
        "meta": meta or {},
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


class SampleStore:
    """小规模写透存储：每次变更整文件重写（万条级样本完全够用）。"""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: list[dict] | None = None
        self._mtime: float | None = None

    # ---- 内部 ----
    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        mtime = self.path.stat().st_mtime
        if self._cache is None or mtime != self._mtime:
            samples = []
            for line in self.path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
            self._cache, self._mtime = samples, mtime
        return self._cache

    def _flush(self, samples: list[dict]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(
            "\n".join(json.dumps(s, ensure_ascii=False) for s in samples) + "\n",
            encoding="utf-8",
        )
        tmp.replace(self.path)
        self._cache, self._mtime = samples, self.path.stat().st_mtime

    # ---- 读 ----
    def all(self) -> list[dict]:
        return list(self._load())

    def __iter__(self) -> Iterator[dict]:
        return iter(self._load())

    def __len__(self) -> int:
        return len(self._load())

    def by_id(self, sample_id: str) -> dict | None:
        for s in self._load():
            if s.get("id") == sample_id:
                return s
        return None

    def find(self, **filters: Any) -> list[dict]:
        out = []
        for s in self._load():
            if all(s.get(k) == v for k, v in filters.items()):
                out.append(s)
        return out

    # ---- 写 ----
    def add(self, sample: dict) -> dict:
        samples = self._load()
        if self.by_id(sample["id"]):
            return self.upsert(sample)
        samples.append(sample)
        self._flush(samples)
        return sample

    def upsert(self, sample: dict) -> dict:
        samples = self._load()
        for i, s in enumerate(samples):
            if s.get("id") == sample["id"]:
                samples[i] = sample
                break
        else:
            samples.append(sample)
        self._flush(samples)
        return sample

    def update(self, sample_id: str, **fields: Any) -> dict | None:
        samples = self._load()
        for i, s in enumerate(samples):
            if s.get("id") == sample_id:
                samples[i] = {**s, **fields}
                self._flush(samples)
                return samples[i]
        return None

    def delete(self, sample_id: str) -> bool:
        samples = self._load()
        rest = [s for s in samples if s.get("id") != sample_id]
        if len(rest) != len(samples):
            self._flush(rest)
            return True
        return False
