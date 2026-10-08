"""全局配置加载：config/system.yaml 为默认值，config/user.yaml 为用户覆盖（gitignored）。"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent
SYSTEM_CONFIG = ROOT / "config" / "system.yaml"
USER_CONFIG = ROOT / "config" / "user.yaml"


def deep_get(d: dict, path: str, default: Any = None) -> Any:
    """按 'a.b.c' 点路径取嵌套配置。"""
    cur: Any = d
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def deep_set(d: dict, path: str, value: Any) -> None:
    keys = path.split(".")
    cur = d
    for key in keys[:-1]:
        cur = cur.setdefault(key, {})
    cur[keys[-1]] = value


class Config:
    """点路径访问的配置对象；save() 时仅落盘 user.yaml 覆盖层。"""

    def __init__(self, base: dict, overrides: dict, user_path: Path = USER_CONFIG):
        self._base = base
        self._overrides = overrides
        self.user_path = user_path

    # ---- 访问 ----
    def get(self, path: str, default: Any = None) -> Any:
        val = deep_get(self._overrides, path)
        if val is not None:
            return val
        return deep_get(self._base, path, default)

    def set(self, path: str, value: Any, persist: bool = True) -> None:
        deep_set(self._overrides, path, value)
        if persist:
            self.save()

    # ---- 常用快捷属性 ----
    @property
    def user_name(self) -> str:
        return str(self.get("user.name", "") or "")

    @property
    def data_dir(self) -> Path:
        d = Path(self.get("paths.data_dir", "data"))
        return d if d.is_absolute() else ROOT / d

    @property
    def samples_file(self) -> Path:
        return self.data_dir / "dataset" / "samples.jsonl"

    @property
    def state_file(self) -> Path:
        return self.data_dir / "agent_state.json"

    @property
    def sessions_dir(self) -> Path:
        return self.data_dir / "sessions"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    def ensure_dirs(self) -> None:
        for p in (
            self.data_dir,
            self.samples_file.parent,
            self.sessions_dir,
            self.exports_dir,
        ):
            p.mkdir(parents=True, exist_ok=True)

    def save(self) -> None:
        self.user_path.parent.mkdir(parents=True, exist_ok=True)
        if self._overrides:
            self.user_path.write_text(
                yaml.safe_dump(self._overrides, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
        elif self.user_path.exists():
            self.user_path.unlink()


def load_config() -> Config:
    base = yaml.safe_load(SYSTEM_CONFIG.read_text(encoding="utf-8")) or {}
    overrides: dict = {}
    if USER_CONFIG.exists():
        overrides = yaml.safe_load(USER_CONFIG.read_text(encoding="utf-8")) or {}
    cfg = Config(copy.deepcopy(base), overrides)
    cfg.ensure_dirs()
    return cfg
