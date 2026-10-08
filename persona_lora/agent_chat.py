"""方案二：双向智能对话采集 Agent。

模式 1 被动常态：正常承接对话，静默打包多轮样本；
模式 2 智能主动：场景缺口/结构缺陷/空闲触发，由 ProactiveEngine 决策。

训练样本角色绑定（关键）：AI 采访者 = user 角色；用户本人 = assistant 角色（原文清洗后一字不改）。
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from .cleaning import clean_text
from .config import Config
from .llm import LLMClient, LLMError
from .proactive import ProactiveEngine
from .scenes import Scene
from .stats import dataset_stats, scene_gaps, usable
from .store import SampleStore, new_sample

FALLBACK_REPLIES = [
    "后来呢？展开说说",
    "然后咋样了哈哈",
    "啊这，然后呢？",
    "有点意思，继续继续",
    "我懂你这感觉，后来你咋处理的？",
]


class PersonaCollector:
    def __init__(
        self,
        cfg: Config,
        store: SampleStore,
        scenes: dict[str, Scene],
        llm: LLMClient | None = None,
    ):
        self.cfg = cfg
        self.store = store
        self.scenes = scenes
        self.llm = llm
        self.engine = ProactiveEngine(cfg, store, scenes)

    # ---------- 会话管理 ----------
    def _session_path(self, session_id: str) -> Path:
        d: Path = self.cfg.sessions_dir
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{session_id}.json"

    def new_session(self, scene_id: str) -> dict:
        scene = self.scenes.get(scene_id)
        opener = random.choice(scene.openers) if scene and scene.openers else "在吗？聊两句～"
        session = {
            "id": time.strftime("s%Y%m%d-%H%M%S"),
            "scene": scene_id,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "last_user_ts": None,
            "proactive_sent": 0,
            "proactive_pending": False,
            "proactive_ts": None,
            "transcript": [
                {"role": "ai", "text": opener,
                 "ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "proactive": False}
            ],
            "rolling_sample_id": None,
            "sealed": False,
        }
        self.save_session(session)
        return session

    def load_session(self, session_id: str) -> dict | None:
        p = self._session_path(session_id)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

    def save_session(self, session: dict) -> None:
        self._session_path(session["id"]).write_text(
            json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # ---------- 核心：被动应答 ----------
    def reply(self, session_id: str, user_text: str) -> dict:
        """用户发言 → AI 承接回复（可能内嵌一次主动话题转向）。"""
        session = self.load_session(session_id)
        if session is None:
            session = self.new_session(self._default_scene_id())
        session["last_user_ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")

        # 主动话题回应判定：正常回应 → 重置无视计数；明确拒绝 → 记一次无视
        if session.get("proactive_pending"):
            if _is_rejection(user_text):
                self.engine.note_ignore(session)
            else:
                self.engine.note_user_reply(session)

        cleaned = clean_text(user_text)

        # 先记录用户消息（AI 回复应基于包含本条的历史生成）
        session["transcript"].append(
            {"role": "human", "text": user_text, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "proactive": False}
        )

        # 静默打包：用户本条 与 紧邻其前的 AI 消息 组成 (user, assistant) 训练对
        # （含独立主动消息场景：主动消息正是等待用户回应的 user 侧发言）
        if cleaned["text"] and len(session["transcript"]) >= 2:
            prev = session["transcript"][-2]
            if prev.get("role") == "ai":
                self._pack(session, prev["text"], cleaned["text"])

        # 中途主动决策（场景缺口/结构缺陷，非空闲）：作为话题转向注入本轮回复
        decision = None
        stats = self._stats()
        gaps = scene_gaps(
            stats, self.scenes, list(stats["by_scene"].keys()),
            str(self.cfg.get("user.mode", "single")) == "multi",
        )
        if cleaned["text"]:
            decision = self.engine.evaluate(session, stats, gaps)
            if decision:
                self.engine.mark_sent(session)

        ai_text = self._interviewer_reply(session, decision)
        session["transcript"].append(
            {"role": "ai", "text": ai_text, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "proactive": bool(decision)}
        )

        self.save_session(session)
        return {
            "reply": ai_text,
            "proactive": decision,
            "dropped": cleaned["dropped"],
            "total_samples": len(usable(self.store.all())),
        }

    # ---------- 核心：独立主动消息（空闲触发） ----------
    def standalone_proactive(self, session_id: str) -> str | None:
        """空闲超时后的独立主动搭话；未触发返回 None。"""
        session = self.load_session(session_id)
        if session is None:
            return None
        idle_min = self._idle_minutes(session)
        stats = self._stats()
        gaps = scene_gaps(
            stats, self.scenes, list(stats["by_scene"].keys()),
            str(self.cfg.get("user.mode", "single")) == "multi",
        )
        decision = self.engine.evaluate(
            session, stats, gaps, idle_minutes_elapsed=idle_min, allow_idle=True
        )
        if not decision:
            return None
        self.engine.mark_sent(session)
        msg = self.engine.build_message(decision, session, self.llm)
        session["transcript"].append(
            {"role": "ai", "text": msg, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
             "proactive": True}
        )
        self.save_session(session)
        return msg

    def close_session(self, session_id: str) -> int:
        """结束会话：封存 rolling 样本，返回本会话累计样本数。"""
        session = self.load_session(session_id)
        if session is None:
            return 0
        session["sealed"] = True
        sid = session.get("rolling_sample_id")
        count = 0
        if sid:
            sample = self.store.by_id(sid)
            if sample:
                sample.setdefault("meta", {})["sealed"] = True
                self.store.upsert(sample)
                count = len(
                    [m for m in sample["messages"] if m.get("role") == "assistant"]
                )
        self.save_session(session)
        return count

    # ---------- 内部 ----------
    def _default_scene_id(self) -> str:
        ids = list(self.cfg.get("user.scenes", []) or self.scenes.keys())
        return ids[0] if ids else "work_communication"

    def _idle_minutes(self, session: dict) -> float:
        last = session.get("last_user_ts") or session.get("created_at")
        if not last:
            return 0.0
        try:
            t = time.mktime(time.strptime(last, "%Y-%m-%dT%H:%M:%S"))
            return max(0.0, (time.time() - t) / 60)
        except ValueError:
            return 0.0

    def _stats(self) -> dict:
        selected = list(self.cfg.get("user.scenes", [])) or list(self.scenes.keys())
        return dataset_stats(self.store.all(), self.scenes, selected)

    def _interviewer_reply(self, session: dict, decision: dict | None) -> str:
        scene = self.scenes.get(session["scene"]) or next(iter(self.scenes.values()))
        name = self.cfg.user_name or "你"
        angles = "\n".join(f"- {a}" for a in scene.interview_angles) or "- 日常寒暄闲聊"
        system = (
            f"你是一位真实、有温度的聊天伙伴，正在和「{name}」日常聊天"
            f"（当前场景：{scene.name}）。\n"
            "你扮演对话里「对方」那一侧（同事/朋友/家人），"
            f"任务是让 {name} 用自己最真实的口吻多说心里话。\n\n"
            "铁律：\n"
            "1. 像真人发消息：短句、口语化、有语气词；一次只聊一个点，绝不连环发问、绝不像问卷。\n"
            f"2. 绝不替 {name} 总结、复述、润色TA的话，不纠正TA的表达。\n"
            f"3. 话题角度参考：\n{angles}\n"
            "4. TA敷衍回复（嗯/收到/哈哈）时，自然换角度，或先随口分享自己的一点看法再轻轻带出话题。\n"
            "5. 不说教、不评价、不居高临下。\n"
            "6. 每次只回 1~2 句，保持真人聊天节奏。"
        )
        if decision:
            system += (
                f"\n\n（本轮特殊任务：请在你回复的最后，像朋友随口提起一样，"
                f"自然把话题引向——{decision['topic']}。不要太刻意。）"
            )

        history = []
        for t in session["transcript"][-12:]:
            history.append(
                {"role": "assistant" if t["role"] == "ai" else "user", "content": t["text"]}
            )
        if not history:
            opener = random.choice(scene.openers) if scene.openers else "在吗？"
            history.append({"role": "user", "content": opener})

        if self.llm is not None:
            try:
                out = self.llm.chat(
                    [{"role": "system", "content": system}] + history,
                    temperature=0.9,
                )
                if out:
                    return out
            except LLMError:
                pass
        # 本地 LLM 不可用时的降级：用话题池当回复，采集不中断
        if decision:
            return decision["topic"]
        return random.choice(FALLBACK_REPLIES)

    def _pack(self, session: dict, ai_text: str, human_text: str) -> None:
        """(AI 话, 用户原话) 追加进 rolling 多轮样本；满了就封存开新条。"""
        max_msgs = int(self.cfg.get("collector.max_sample_messages", 12))
        add = [{"role": "user", "content": ai_text},
               {"role": "assistant", "content": human_text}]
        rid = session.get("rolling_sample_id")
        if rid:
            sample = self.store.by_id(rid)
            if sample is not None:
                if len(sample["messages"]) + len(add) <= max_msgs:
                    sample["messages"] += add
                    self.store.upsert(sample)
                    return
                sample.setdefault("meta", {})["sealed"] = True
                self.store.upsert(sample)
        sample = new_sample(
            source="agent_chat",
            scene=session["scene"],
            messages=add,
            status="approved",
        )
        self.store.add(sample)
        session["rolling_sample_id"] = sample["id"]


def _is_rejection(text: str) -> bool:
    t = text.strip()
    if len(t) > 12:
        return False
    for word in ("不想聊", "别问", "不想说", "算了", "没兴趣", "滚", "烦", "打住"):
        if word in t:
            return True
    return False
