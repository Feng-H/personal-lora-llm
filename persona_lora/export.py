"""训练集导出：统一 Qwen messages jsonl（train/validation + 数据集卡片）。"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .scenes import Scene
from .stats import dataset_stats, scene_gaps, usable


class ExportError(RuntimeError):
    pass


def export_dataset(
    samples: list[dict],
    scenes: dict[str, Scene],
    selected: list[Scene],
    cfg,
    out_dir: Path,
    multi_mode: bool,
    min_total: int = 70,
) -> dict:
    """过滤 → 校验 → 切分 → 落盘。返回导出摘要；不满足硬性阈值抛 ExportError。"""
    usable_samples = usable(samples)
    if len(usable_samples) < min_total:
        raise ExportError(
            f"有效样本仅 {len(usable_samples)} 条，低于最低阈值 {min_total} 条（基础版风格）。"
        )
    # 多场景模式强制校验：每个勾选场景都须达到最低阈值，防止风格混杂
    stats = dataset_stats(samples, scenes, [s.id for s in selected])
    gaps = scene_gaps(stats, scenes, [s.id for s in selected], multi_mode)
    weak = [g for g in gaps if g["gap"] > 0]
    if multi_mode and weak:
        detail = "、".join(f"{g['name']}({g['have']}/{g['need']})" for g in weak)
        raise ExportError(f"多场景模式强制校验未通过，以下场景样本不足：{detail}")

    rows = []
    for s in usable_samples:
        scene = scenes.get(s.get("scene", ""))
        if not scene:
            continue
        system = scene.build_system_prompt(cfg.user_name)
        messages = [{"role": "system", "content": system}] + [
            {"role": m["role"], "content": m["content"]}
            for m in s.get("messages", [])
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        if len(messages) < 2 or messages[-1]["role"] != "assistant":
            continue
        rows.append({"messages": messages})

    rng = random.Random(int(cfg.get("export.seed", 42)))
    rng.shuffle(rows)
    val_ratio = float(cfg.get("export.val_ratio", 0.05))
    n_val = max(1, int(len(rows) * val_ratio)) if len(rows) >= 20 else 0
    val_rows, train_rows = rows[:n_val], rows[n_val:]

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "train.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in train_rows) + "\n",
        encoding="utf-8",
    )
    if val_rows:
        (out_dir / "validation.jsonl").write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in val_rows) + "\n",
            encoding="utf-8",
        )

    card = {
        "train_samples": len(train_rows),
        "validation_samples": len(val_rows),
        "total_usable": len(usable_samples),
        "scenes": {s.id: s.name for s in selected},
        "mode": "multi" if multi_mode else "single",
        "stats": stats,
    }
    (out_dir / "dataset_card.json").write_text(
        json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return card
