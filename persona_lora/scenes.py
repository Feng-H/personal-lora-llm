"""场景管理：加载 config/scenes/*.yaml，构建场景对象。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .config import ROOT

SCENES_DIR = ROOT / "config" / "scenes"


@dataclass
class Scene:
    id: str
    name: str
    description: str = ""
    icon: str = "🏷️"
    system_prompt: str = ""
    min_samples_single: int = 70
    min_samples_multi: int = 45
    questionnaire: str = ""
    retrieval_queries: list[str] = field(default_factory=list)
    interview_angles: list[str] = field(default_factory=list)
    openers: list[str] = field(default_factory=list)
    proactive_topics: list[str] = field(default_factory=list)

    def build_system_prompt(self, user_name: str = "") -> str:
        name = (user_name or "你").strip()
        return self.system_prompt.replace("{user_name}", name).strip()

    def min_samples(self, multi_mode: bool) -> int:
        return self.min_samples_multi if multi_mode else self.min_samples_single

    @property
    def questionnaire_path(self) -> Path:
        return ROOT / self.questionnaire

    @classmethod
    def from_dict(cls, d: dict) -> Scene:
        return cls(
            id=str(d.get("id", "")),
            name=str(d.get("name", "")),
            description=str(d.get("description", "")),
            icon=str(d.get("icon", "🏷️")),
            system_prompt=str(d.get("system_prompt", "")),
            min_samples_single=int(d.get("min_samples_single", 70)),
            min_samples_multi=int(d.get("min_samples_multi", 45)),
            questionnaire=str(d.get("questionnaire", "")),
            retrieval_queries=list(d.get("retrieval_queries", [])),
            interview_angles=list(d.get("interview_angles", [])),
            openers=list(d.get("openers", [])),
            proactive_topics=list(d.get("proactive_topics", [])),
        )


def load_scenes() -> dict[str, Scene]:
    scenes: dict[str, Scene] = {}
    for path in sorted(SCENES_DIR.glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            scene = Scene.from_dict(data)
            if scene.id:
                scenes[scene.id] = scene
        except yaml.YAMLError:
            continue
    return scenes


def selected_scenes(cfg, scenes: dict[str, Scene] | None = None) -> list[Scene]:
    """返回用户当前勾选的场景列表。"""
    scenes = scenes if scenes is not None else load_scenes()
    ids = cfg.get("user.scenes", []) or []
    return [scenes[sid] for sid in ids if sid in scenes]

def is_multi_mode(cfg) -> bool:
    return str(cfg.get("user.mode", "single")) == "multi"
