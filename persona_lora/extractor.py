"""LLM 智能问答对抽取：严格角色绑定 + 只标记不删除，人工审核兜底。"""
from __future__ import annotations

from .llm import LLMClient, LLMError
from .scenes import Scene
from .slicer import window_text, window_turns
from .store import new_sample

JUDGE_SYSTEM = "你是一个严格的数据质检员，只输出 JSON，不输出任何其他文字。"

JUDGE_PROMPT = """下面是一段从 IM 聊天记录切出的窗口。
「对方」= 训练时的 user 角色；「我」= 用户本人，训练时的 assistant 角色（原文一字不改）。
当前预期场景：{scene_name}（{scene_desc}）

对话内容：
---
{transcript}
---

请判断这段对话作为该场景训练样本的质量，只输出如下 JSON：
{{"scene_match": true 或 false, "quality": "good" 或 "low", "flags": [], "reason": "一句话理由"}}

判定规则：
- scene_match：内容是否属于预期场景（false = 场景错配）
- 几乎全是寒暄/单字/无意义内容、没有信息量 → quality=low，flags 加 "低质量"
- 含隐私明文（手机号/身份证/住址/银行卡/密码）→ flags 加 "风险"
- 意义不明、刷屏、疑似机器人消息 → flags 加 "人工复核"
flags 只能从 ["低质量", "风险", "人工复核"] 里选，没有就给空数组。"""


def llm_judge(transcript: str, scene: Scene, llm: LLMClient | None) -> dict | None:
    """LLM 质检；模型不可用时返回 None（走纯规则降级）。"""
    if llm is None:
        return None
    try:
        result = llm.ask_json(
            JUDGE_PROMPT.format(
                scene_name=scene.name,
                scene_desc=scene.description,
                transcript=transcript[:3000],
            ),
            system=JUDGE_SYSTEM,
        )
    except LLMError:
        return None
    return result if isinstance(result, dict) else None


def build_sample(window: list, scene: Scene, llm: LLMClient | None, sim: float) -> dict | None:
    """窗口 → 待审核训练样本。

    铁律：assistant 侧永远取用户本人原文（清洗仅打码隐私/剔除纯噪声），
    LLM 只负责打标记，绝不改写、绝不定稿——所有样本 status=pending 交人工审核。
    """
    turns, clean_flags = window_turns(window)
    if len(turns) < 2:
        return None

    flags: list[str] = []
    for f in clean_flags:
        label = f.split(":", 1)[0]
        if label == "风险" and "风险" not in flags:
            flags.append("风险")

    judgment = llm_judge(window_text(window), scene, llm)
    if judgment:
        scene_match = judgment.get("scene_match")
        if scene_match is not None and not scene_match:
            flags.append("场景错配")
        for f in judgment.get("flags", []):
            if f in ("低质量", "风险", "人工复核") and f not in flags:
                flags.append(f)

    meta: dict = {"sim": round(sim, 3)}
    if judgment and judgment.get("reason"):
        meta["judge_reason"] = str(judgment["reason"])[:200]

    return new_sample(
        source="im_import",
        scene=scene.id,
        messages=turns,
        flags=flags,
        status="pending",
        meta=meta,
    )
