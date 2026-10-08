#!/usr/bin/env python3
"""把 config/scenes/*.yaml + questionnaires/*.csv 构建成网页题库 web/data/bank.js。

单一数据源永远是 CSV + YAML；网页端只消费生成产物，杜绝双头维护漂移。
生成物为确定性输出（无时间戳），保证 --check 校验稳定。

用法：
    python scripts/build_web_bank.py           # 生成 web/data/bank.js
    python scripts/build_web_bank.py --check   # CI 校验：生成物与仓库版本一致，否则退出码 1
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from persona_lora import __version__, questionnaire  # noqa: E402
from persona_lora.scenes import load_scenes  # noqa: E402

OUT_PATH = ROOT / "web" / "data" / "bank.js"


def build_bank() -> dict:
    scenes = load_scenes()
    pack = {
        "version": __version__,
        "scenes": [],
    }
    for sid, scene in scenes.items():
        bank = questionnaire.load_bank(scene)
        questions = [
            {
                "idx": b["idx"],
                "qid": questionnaire.qid(sid, b["idx"]),
                "context": b["context"],
                "question": b["question"],
            }
            for b in bank
        ]
        pack["scenes"].append(
            {
                "id": scene.id,
                "name": scene.name,
                "icon": scene.icon,
                "description": scene.description,
                "systemPrompt": scene.system_prompt.strip(),
                "minSamplesSingle": scene.min_samples_single,
                "minSamplesMulti": scene.min_samples_multi,
                "questions": questions,
            }
        )
    return pack


def render(pack: dict) -> str:
    body = json.dumps(pack, ensure_ascii=False)
    return (
        "/* 由 scripts/build_web_bank.py 生成，勿手改。\n"
        " * 数据源：config/scenes/*.yaml + questionnaires/*.csv（改题库请改源头后重新生成）\n"
        " * 生成命令：python scripts/build_web_bank.py\n */\n"
        '(typeof window !== "undefined" ? window : globalThis).PERSONA_BANK = '
        + body
        + ";\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="构建网页题库 bank.js")
    parser.add_argument("--check", action="store_true", help="校验生成物与仓库版本一致（CI 用）")
    args = parser.parse_args()

    pack = build_bank()
    text = render(pack)

    if args.check:
        if not OUT_PATH.exists():
            print(f"❌ {OUT_PATH} 不存在：请先运行 python scripts/build_web_bank.py 并提交", file=sys.stderr)
            sys.exit(1)
        if OUT_PATH.read_text(encoding="utf-8") != text:
            print(
                "❌ web/data/bank.js 与题库源头不一致：请运行 python scripts/build_web_bank.py 并提交",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"✅ bank.js 与源头一致（{OUT_PATH}）")
        return

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")
    total = sum(len(s["questions"]) for s in pack["scenes"])
    print(f"✅ 已生成 {OUT_PATH.relative_to(ROOT)}：{len(pack['scenes'])} 场景 / {total} 题")


if __name__ == "__main__":
    main()
