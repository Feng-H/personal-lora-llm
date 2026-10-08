"""方案三：IM 历史聊天记录智能抽取（存量批量扩容）。

RAG/向量检索仅用于训练集素材预处理；推理阶段无任何检索。
流程：本地文件解析 → 主题切片 → 本地 Embedding → 场景检索筛选 → LLM 质检标记 → 人工审核。
"""
from __future__ import annotations

import re

from .config import Config
from .llm import LLMClient
from .scenes import Scene
from .store import SampleStore
from .embedding import LocalEmbedder, cosine_matrix
from .extractor import build_sample
from .slicer import ChatMsg, slice_windows, window_text

# 各类导出格式的行头（名字与时间的多种排列）
_HEADER_PATTERNS = [
    # 张三 2024-05-01 10:23:45 / 张三 2024/5/1 10:23
    re.compile(
        r"^(?P<name>\S{1,24}?)\s+(?P<ts>\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*$"
    ),
    # 2024-05-01 10:23:45 张三
    re.compile(
        r"^(?P<ts>\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{1,2}(?::\d{1,2})?)\s+(?P<name>\S{1,24}?)\s*$"
    ),
    # [2024-05-01 10:23:45] 张三: 消息
    re.compile(r"^\[(?P<ts>[^\]]{5,24})\]\s*(?P<name>\S{1,24}?)[:：]\s*(?P<msg>.*)$"),
    # 张三 [10:23] 消息
    re.compile(r"^(?P<name>\S{1,24}?)\s*\[\d{1,2}:\d{1,2}(?::\d{1,2})?\]\s*(?P<msg>.*)$"),
    # 张三: 消息（名字含中文/字母数字，最长24，冒号前无句读）
    re.compile(r"^(?P<name>[\w\-\u4e00-\u9fff·]{1,16})[:：]\s*(?P<msg>.+)$"),
]
_TS_INLINE = re.compile(r"^(?P<ts>\d{1,2}:\d{1,2}(?::\d{1,2})?)\s*(?P<msg>.*)$")
_SKIP_LINE = re.compile(
    r"^\s*([-*=~—─═]{3,}|=+$|消息记录|聊天记录|————|插件|导出时间|====)"
)


def parse_chat_lines(text: str, my_names: list[str]) -> list[ChatMsg]:
    """容错解析：识别 5 类常见行头；未匹配行视为上一条消息的续行（多行消息）。"""
    from .slicer import parse_ts as _parse_ts

    my = {n.strip() for n in my_names if n.strip()}
    msgs: list[ChatMsg] = []
    pending: dict | None = None  # 等待消息体的 (name, ts)
    cur: ChatMsg | None = None

    def flush_pending() -> None:
        nonlocal pending
        pending = None

    for raw in text.splitlines():
        line = raw.rstrip("\n").strip()
        if not line or _SKIP_LINE.match(line):
            continue

        matched = False
        # 1) 「名字 时间」行头（消息体在下一行）
        m = _HEADER_PATTERNS[0].match(line) or _HEADER_PATTERNS[1].match(line)
        if m:
            flush_pending()
            pending = {
                "name": m.group("name"),
                "ts": _parse_ts(m.group("ts")),
            }
            cur = None
            matched = True
        # 2) 行内带名字的格式
        if not matched:
            m = _HEADER_PATTERNS[2].match(line) or _HEADER_PATTERNS[3].match(line) or _HEADER_PATTERNS[4].match(line)
            if m and m.group("msg").strip():
                flush_pending()
                ts = _parse_ts(m.group("ts")) if m.groupdict().get("ts") else None
                body = m.group("msg").strip()
                ts_m = _TS_INLINE.match(body)
                if ts is None and ts_m:
                    body = ts_m.group("msg").strip()
                cur = ChatMsg(
                    speaker=m.group("name"),
                    is_me=m.group("name") in my,
                    text=body,
                    ts=ts,
                )
                msgs.append(cur)
                matched = True
        # 3) 消息体续行
        if not matched:
            if pending is not None:
                cur = ChatMsg(
                    speaker=pending["name"],
                    is_me=pending["name"] in my,
                    text=line,
                    ts=pending["ts"],
                )
                msgs.append(cur)
                flush_pending()
            elif cur is not None:
                cur.text += "\n" + line
    return msgs


def run_pipeline(
    text: str,
    my_names: list[str],
    cfg: Config,
    scenes: dict[str, Scene],
    selected_ids: list[str],
    store: SampleStore,
    llm: LLMClient | None,
    progress=None,  # callable(stage: str, done: int, total: int)
) -> dict:
    """完整流水线：解析 → 切片 → 向量 → 场景筛选 → LLM 标记 → 入库(pending)。"""
    def _p(stage: str, done: int, total: int) -> None:
        if progress:
            progress(stage, done, total)

    msgs = parse_chat_lines(text, my_names)
    _p("解析聊天记录", len(msgs), len(msgs))
    if not msgs:
        return {"parsed": 0, "windows": 0, "kept": 0, "samples": 0}

    gap = int(cfg.get("im_import.time_gap_minutes", 30))
    min_r = int(cfg.get("im_import.min_rounds", 4))
    max_r = int(cfg.get("im_import.max_rounds", 8))
    windows = slice_windows(msgs, gap_minutes=gap, min_rounds=min_r, max_rounds=max_r)
    _p("主题切片", len(windows), len(windows))
    if not windows:
        return {"parsed": len(msgs), "windows": 0, "kept": 0, "samples": 0}

    # 本地向量（不上传任何内容）
    embedder = LocalEmbedder(str(cfg.get("embedding.model", "BAAI/bge-small-zh-v1.5")))
    wvecs = embedder.embed([window_text(w) for w in windows])
    sel_scenes = [scenes[sid] for sid in selected_ids if sid in scenes]
    qvecs = embedder.embed(
        [q for s in sel_scenes for q in (s.retrieval_queries or [s.name])]
    )
    threshold = float(cfg.get("embedding.scene_sim_threshold", 0.32))

    # 每个场景的查询向量块 → 窗口得分 = 与该场景任一关键词的最大相似度
    scores = cosine_matrix(wvecs, qvecs)
    # 直接逐窗取最优场景
    kept: list[tuple[int, list, float]] = []  # (scene_index, window, sim)
    for wi in range(len(windows)):
        best_si, best_score, off = -1, -1.0, 0
        for si, scene in enumerate(sel_scenes):
            n_q = len(scene.retrieval_queries or [scene.name])
            s = float(scores[wi, off : off + n_q].max()) if n_q else -1.0
            off += n_q
            if s > best_score:
                best_si, best_score = si, s
        if best_si >= 0 and best_score >= threshold:
            kept.append((best_si, windows[wi], best_score))
    _p("场景向量检索", len(kept), len(windows))

    added = 0
    for i, (si, win, sim) in enumerate(kept):
        sample = build_sample(win, sel_scenes[si], llm, sim)
        if sample is not None:
            store.add(sample)
            added += 1
        _p("LLM 质检与入库", i + 1, len(kept))

    return {
        "parsed": len(msgs),
        "windows": len(windows),
        "kept": len(kept),
        "samples": added,
        "pending_review": added,
    }
