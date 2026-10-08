"""本地 OpenAI 兼容 LLM 客户端（Ollama / LM Studio / llama.cpp server）。"""
from __future__ import annotations

import importlib
import json
import re
from typing import cast

CODE_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class LLMError(RuntimeError):
    pass


def extract_json(text: str):
    """从 LLM 回复中稳健抽取 JSON（容忍代码围栏/前后废话）。失败返回 None。"""
    if not text:
        return None
    candidates = [m.group(1) for m in CODE_FENCE.finditer(text)]
    candidates.append(text)
    for cand in candidates:
        cand = cand.strip()
        # 截取首个 { 到最后一个 } / [ ... ]
        for lhs, rhs in (("{", "}"), ("[", "]")):
            i, j = cand.find(lhs), cand.rfind(rhs)
            if i != -1 and j > i:
                try:
                    return json.loads(cand[i : j + 1])
                except json.JSONDecodeError:
                    continue
    return None


class LLMClient:
    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen3:8b",
        api_key: str = "ollama",
        temperature: float = 0.85,
        max_tokens: int = 512,
        timeout: float = 180.0,
    ):
        # 延迟动态加载 openai SDK（可选依赖，缺失时给出友好报错）
        try:
            openai = importlib.import_module("openai")
        except ImportError as e:  # pragma: no cover
            raise LLMError("缺少依赖 openai：pip install openai") from e
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = openai.OpenAI(
            base_url=base_url, api_key=api_key or "ollama", timeout=timeout
        )

    @classmethod
    def from_config(cls, cfg) -> LLMClient:
        return cls(
            base_url=cfg.get("llm.base_url", "http://localhost:11434/v1"),
            model=cfg.get("llm.model", "qwen3:8b"),
            api_key=cfg.get("llm.api_key", "ollama"),
            temperature=float(cfg.get("llm.temperature", 0.85)),
            max_tokens=int(cfg.get("llm.max_tokens", 512)),
        )

    def chat(
        self,
        messages: list[dict],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.model,
                messages=cast(list, messages),
                temperature=self.temperature if temperature is None else temperature,
                max_tokens=self.max_tokens if max_tokens is None else max_tokens,
            )
        except Exception as e:  # noqa: BLE001 —— 统一转成 LLMError，调用方都有降级路径
            raise LLMError(f"LLM 调用失败（{self.model}）: {e}") from e
        content = resp.choices[0].message.content or ""
        # 兼容本地模型输出 <think>…</think>（如 Qwen3 思考模式）
        return re.sub(r"<think>[\s\S]*?</think>", "", content).strip()

    def ask_json(self, prompt: str, system: str = "") -> dict | list | None:
        text = self.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": prompt}]
            if system
            else [{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return extract_json(text)
