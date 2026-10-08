"""Streamlit 工作台共享组件：配置/场景/存储/LLM 单例与统计。"""
from __future__ import annotations

import streamlit as st  # pyright: ignore[reportMissingImports]
from persona_lora import load_config, load_scenes  # pyright: ignore[reportMissingImports]
from persona_lora.llm import LLMClient  # pyright: ignore[reportMissingImports]
from persona_lora.stats import dataset_stats  # pyright: ignore[reportMissingImports]
from persona_lora.store import SampleStore  # pyright: ignore[reportMissingImports]


@st.cache_resource
def get_cfg():
    return load_config()


@st.cache_resource
def get_scenes():
    return load_scenes()


@st.cache_resource
def get_store() -> SampleStore:
    return SampleStore(get_cfg().samples_file)


@st.cache_resource
def get_llm() -> LLMClient | None:
    """本地 OpenAI 兼容客户端；服务不可用时返回 None（各功能均有降级路径）。"""
    try:
        return LLMClient.from_config(get_cfg())
    except Exception:  # noqa: BLE001 —— 采集界面允许无 LLM 运行
        return None


def llm_status() -> tuple[bool, str]:
    client = get_llm()
    if client is None:
        return False, "未配置"
    try:
        client.chat([{"role": "user", "content": "ping"}], max_tokens=8)
        return True, client.model
    except Exception:  # noqa: BLE001
        return False, client.model


def selected_scene_objs():
    cfg, scenes = get_cfg(), get_scenes()
    ids = cfg.get("user.scenes", []) or []
    return [scenes[s] for s in ids if s in scenes]


def save_user_settings(name: str, mode: str, scene_ids: list[str]) -> None:
    cfg = get_cfg()
    cfg.set("user.name", name.strip(), persist=True)
    cfg.set("user.mode", mode, persist=True)
    cfg.set("user.scenes", scene_ids, persist=True)


def fresh_stats() -> dict:
    cfg = get_cfg()
    scenes = get_scenes()
    store = get_store()
    selected = list(cfg.get("user.scenes", [])) or list(scenes.keys())
    return dataset_stats(store.all(), scenes, selected)
