"""数据集统计：场景缺口检测、结构缺陷检测（主动采集引擎的输入）。"""
from __future__ import annotations


def usable(samples: list[dict]) -> list[dict]:
    """可训练样本：问卷/对话采集默认可用；IM 抽取必须人工审核通过。"""
    return [
        s
        for s in samples
        if s.get("source") in ("questionnaire", "agent_chat")
        or s.get("status") == "approved"
    ]


def dataset_stats(samples: list[dict], scenes: dict, selected_ids: list[str]) -> dict:
    u = usable(samples)
    by_scene: dict[str, dict] = {}
    for sid in selected_ids:
        items = [s for s in u if s.get("scene") == sid]
        assistant_texts = [
            m["content"]
            for s in items
            for m in s.get("messages", [])
            if m.get("role") == "assistant"
        ]
        short = [a for a in assistant_texts if len(a) <= 4]
        multi = [s for s in items if len(s.get("messages", [])) > 3]
        by_scene[sid] = {
            "name": scenes[sid].name if sid in scenes else sid,
            "count": len(items),
            "assistant_turns": len(assistant_texts),
            "avg_assistant_len": (
                round(sum(len(a) for a in assistant_texts) / len(assistant_texts), 1)
                if assistant_texts
                else 0
            ),
            "short_reply_ratio": round(len(short) / len(assistant_texts), 2)
            if assistant_texts
            else 0.0,
            "multi_turn_ratio": round(len(multi) / len(items), 2) if items else 0.0,
        }
    all_assistant = [
        m["content"] for s in u for m in s.get("messages", []) if m.get("role") == "assistant"
    ]
    return {
        "total": len(u),
        "by_source": {
            src: len([s for s in u if s.get("source") == src])
            for src in ("questionnaire", "agent_chat", "im_import")
        },
        "by_scene": by_scene,
        "quality": {
            "avg_assistant_len": round(
                sum(len(a) for a in all_assistant) / len(all_assistant), 1
            )
            if all_assistant
            else 0,
            "short_reply_ratio": round(
                len([a for a in all_assistant if len(a) <= 4]) / len(all_assistant), 2
            )
            if all_assistant
            else 0.0,
            "multi_turn_ratio": round(
                len([s for s in u if len(s.get("messages", [])) > 3]) / len(u), 2
            )
            if u
            else 0.0,
        },
        "pending_review": len([s for s in samples if s.get("status") == "pending"]),
    }


def scene_gaps(
    stats: dict, scenes: dict, selected_ids: list[str], multi_mode: bool
) -> list[dict]:
    """按缺口比例排序的场景缺口表：ratio=1 表示达标。"""
    gaps = []
    for sid in selected_ids:
        scene = scenes.get(sid)
        if not scene:
            continue
        need = scene.min_samples(multi_mode)
        have = stats["by_scene"].get(sid, {}).get("count", 0)
        gaps.append(
            {
                "scene": sid,
                "name": scene.name,
                "have": have,
                "need": need,
                "ratio": round(have / need, 2) if need else 1.0,
                "gap": max(0, need - have),
            }
        )
    return sorted(gaps, key=lambda g: g["ratio"])


def structure_deficiency(stats: dict, cfg) -> tuple[bool, str]:
    """结构缺陷检测：敷衍短句占比过高 / 长句多轮样本过少。"""
    q = stats["quality"]
    warn_ratio = float(cfg.get("collector.short_reply_ratio_warn", 0.5))
    if q["short_reply_ratio"] >= warn_ratio and stats["total"] >= 20:
        return True, f"敷衍短句占比 {q['short_reply_ratio']:.0%} 过高，缺少深度表达样本"
    if q["multi_turn_ratio"] < 0.2 and stats["total"] >= 40:
        return True, "多轮对话样本占比过低，缺少上下文承接样本"
    return False, ""
