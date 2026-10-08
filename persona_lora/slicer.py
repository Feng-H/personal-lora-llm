"""对话主题切片：把杂乱的 IM 流水切成 4–8 轮一个主题窗口。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .cleaning import clean_text


@dataclass
class ChatMsg:
    speaker: str
    is_me: bool
    text: str
    ts: datetime | None = None


def parse_ts(raw: str) -> datetime | None:
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
    ):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def split_by_gap(msgs: list[ChatMsg], gap_minutes: int) -> list[list[ChatMsg]]:
    """相邻消息时间差超过阈值 → 切分新对话（无时间戳则不切）。"""
    blocks: list[list[ChatMsg]] = []
    cur: list[ChatMsg] = []
    for m in msgs:
        if (
            cur
            and m.ts is not None
            and cur[-1].ts is not None
            and (m.ts - cur[-1].ts).total_seconds() > gap_minutes * 60
        ):
            blocks.append(cur)
            cur = []
        cur.append(m)
    if cur:
        blocks.append(cur)
    return blocks


def slice_windows(
    msgs: list[ChatMsg],
    gap_minutes: int = 30,
    min_rounds: int = 4,
    max_rounds: int = 8,
) -> list[list[ChatMsg]]:
    """时间切块 → 按 max_rounds 切窗 → 丢弃不足 min_rounds 的碎窗。"""
    windows: list[list[ChatMsg]] = []
    for block in split_by_gap(msgs, gap_minutes):
        for i in range(0, len(block), max_rounds):
            win = block[i : i + max_rounds]
            if len(win) >= min_rounds:
                windows.append(win)
    return windows


def window_text(window: list[ChatMsg]) -> str:
    """窗口的可读表示（供 embedding 与 LLM 质检）。"""
    lines = []
    for m in window:
        lines.append(f"{'我' if m.is_me else '对方'}：{m.text}")
    return "\n".join(lines)


def window_turns(window: list[ChatMsg]) -> tuple[list[dict], list[str]]:
    """窗口 → 训练消息序列：对方=user、我=assistant，原文一字不改。

    - 剔除纯噪声消息（乱码/表情占位/系统消息）
    - 隐私明文打码并冒泡【风险】标记
    - 相邻同角色消息用换行合并（保真合并，不改写）
    - 结尾若是 user（对方最后一句话没人接）→ 丢弃该轮
    """
    turns: list[dict] = []
    flags: list[str] = []
    for m in window:
        cleaned = clean_text(m.text)
        if cleaned["dropped"]:
            continue
        flags.extend(cleaned["flags"])
        role = "assistant" if m.is_me else "user"
        if turns and turns[-1]["role"] == role:
            turns[-1]["content"] += "\n" + cleaned["text"]
        else:
            turns.append({"role": role, "content": cleaned["text"]})
    while turns and turns[-1]["role"] != "assistant":
        turns.pop()
    return turns, flags
