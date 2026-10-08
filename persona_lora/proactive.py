"""主动发起引擎（独创核心）：场景缺口 > 结构缺陷 > 空闲定时，严格限流防骚扰。"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from .llm import LLMClient, LLMError
from .scenes import Scene
from .stats import structure_deficiency


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class ProactiveEngine:
    def __init__(self, cfg, store, scenes: dict[str, Scene]):
        self.cfg = cfg
        self.store = store
        self.scenes = scenes
        self.state_path: Path = cfg.state_file

    # ---------- 持久化状态（跨会话） ----------
    def _load_state(self) -> dict:
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"daily": {"date": "", "count": 0}, "consecutive_ignores": 0, "permanent_passive": False}

    def _save_state(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _bump_daily(self, state: dict) -> None:
        today = time.strftime("%Y-%m-%d")
        if state["daily"]["date"] != today:
            state["daily"] = {"date": today, "count": 0}

    # ---------- 评估 ----------
    def evaluate(
        self,
        session: dict,
        stats: dict,
        gaps: list[dict],
        idle_minutes_elapsed: float = 0.0,
        allow_idle: bool = False,
    ) -> dict | None:
        """返回主动发起决策 {reason, scene_id, topic}；不触发返回 None。

        优先级：场景样本缺口 > 样本结构缺陷 > 空闲定时。
        限流：达标关闭 / 永久被动 / 单轮会话 1 次 / 单日上限。
        """
        state = self._load_state()
        if state["permanent_passive"]:
            return None
        if stats.get("total", 0) >= int(self.cfg.get("collector.optimal_target", 120)):
            return None  # 样本达标 → 自动关闭所有主动采集
        if session.get("proactive_sent", 0) >= int(
            self.cfg.get("collector.max_proactive_per_session", 1)
        ):
            return None
        self._bump_daily(state)
        if state["daily"]["count"] >= int(self.cfg.get("collector.max_proactive_per_day", 3)):
            return None

        selected_ids = list(stats.get("by_scene", {}).keys())
        scenes = self.scenes

        # 1) 场景样本缺口（最高优先级）
        weak = [g for g in gaps if g["gap"] > 0]
        if weak:
            g = weak[0]
            scene = scenes.get(g["scene"])
            if scene and scene.proactive_topics:
                return {
                    "reason": "scene_gap",
                    "scene_id": scene.id,
                    "scene_name": scene.name,
                    "topic": random.choice(scene.proactive_topics),
                }

        # 2) 样本结构缺陷（短句敷衍过多 → 主动发起深度表达话题）
        deficient, why = structure_deficiency(stats, self.cfg)
        if deficient:
            fallback = scenes.get(selected_ids[0]) if selected_ids else None
            pool = [
                scenes[sid]
                for sid in selected_ids
                if sid in scenes and scenes[sid].proactive_topics
            ]
            scene = random.choice(pool) if pool else fallback
            if scene and scene.proactive_topics:
                return {
                    "reason": "structure",
                    "scene_id": scene.id,
                    "scene_name": scene.name,
                    "topic": random.choice(scene.proactive_topics),
                }

        # 3) 空闲定时触发（温和开启新话题）
        if allow_idle and idle_minutes_elapsed >= float(
            self.cfg.get("collector.idle_minutes", 7)
        ):
            pool = [
                scenes[sid]
                for sid in selected_ids
                if sid in scenes and scenes[sid].proactive_topics
            ]
            if pool:
                scene = random.choice(pool)
                return {
                    "reason": "idle",
                    "scene_id": scene.id,
                    "scene_name": scene.name,
                    "topic": random.choice(scene.proactive_topics),
                }
        return None

    # ---------- 记账 ----------
    def mark_sent(self, session: dict) -> None:
        session["proactive_sent"] = session.get("proactive_sent", 0) + 1
        session["proactive_pending"] = True
        session["proactive_ts"] = _now_iso()
        state = self._load_state()
        self._bump_daily(state)
        state["daily"]["count"] += 1
        self._save_state(state)

    def note_user_reply(self, session: dict) -> None:
        """用户正常回应了主动话题 → 重置无视计数。"""
        session["proactive_pending"] = False
        state = self._load_state()
        state["consecutive_ignores"] = 0
        self._save_state(state)

    def note_ignore(self, session: dict) -> None:
        """用户无视/拒绝主动话题 → 计数，连续 2 次永久降级被动模式。"""
        session["proactive_pending"] = False
        state = self._load_state()
        state["consecutive_ignores"] += 1
        if state["consecutive_ignores"] >= int(self.cfg.get("collector.ignore_limit", 2)):
            state["permanent_passive"] = True
        self._save_state(state)

    # ---------- 消息生成 ----------
    def build_message(
        self, decision: dict, session: dict, llm: LLMClient | None
    ) -> str:
        """把话题变成一句自然的话：优先承接上下文，无上下文用温和开场。"""
        scene = self.scenes.get(decision["scene_id"])
        openers = scene.openers if scene else []
        opener = random.choice(openers) if openers else ""
        tail = [t["text"] for t in session.get("transcript", [])[-4:]]
        tail_text = "\n".join(tail)[-600:]

        if llm is not None:
            try:
                msg = llm.chat(
                    [
                        {
                            "role": "system",
                            "content": (
                                "你是用户的好朋友，现在想自然地开启一个新话题，"
                                "让TA多用真实口吻聊聊心里话。只输出你要发送的那条消息本身，"
                                "1~2 句、口语化、绝不能有问卷感。"
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"想聊的话题方向：{decision['topic']}\n"
                                f"（如果和最近聊的内容有关联就自然承接，没有就直接温和开场）\n"
                                f"最近的对话：\n{tail_text or '（刚开始聊）'}"
                            ),
                        },
                    ],
                    temperature=0.9,
                    max_tokens=120,
                )
                if msg:
                    return msg
            except LLMError:
                pass
        return f"{opener}{decision['topic']}"
