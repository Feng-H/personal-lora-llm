"""命令行入口：python -m persona_lora.cli <stats|export|im-import|import-answers>"""
from __future__ import annotations

import argparse
import csv as csv_mod
import json
import sys
from pathlib import Path

from .config import load_config
from .export import ExportError, export_dataset
from .im_import import run_pipeline
from .llm import LLMClient
from .questionnaire import import_answers, import_csv_rows
from .scenes import load_scenes, selected_scenes
from .stats import dataset_stats, scene_gaps
from .store import SampleStore


def _ctx():
    cfg = load_config()
    scenes = load_scenes()
    store = SampleStore(cfg.samples_file)
    return cfg, scenes, store


def cmd_stats(_args: argparse.Namespace) -> None:
    cfg, scenes, store = _ctx()
    sel_ids = list(cfg.get("user.scenes", [])) or list(scenes.keys())
    multi = cfg.get("user.mode", "single") == "multi"
    stats = dataset_stats(store.all(), scenes, sel_ids)
    gaps = scene_gaps(stats, scenes, sel_ids, multi)
    print(json.dumps({"stats": stats, "gaps": gaps}, ensure_ascii=False, indent=2))


def cmd_export(_args: argparse.Namespace) -> None:
    cfg, scenes, store = _ctx()
    sel = selected_scenes(cfg, scenes)
    multi = cfg.get("user.mode", "single") == "multi"
    try:
        card = export_dataset(
            store.all(), scenes, sel, cfg, cfg.exports_dir, multi,
            min_total=int(cfg.get("collector.basic_target", 70)),
        )
    except ExportError as e:
        print(f"❌ {e}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(card, ensure_ascii=False, indent=2))
    print(f"✅ 已写入 {cfg.exports_dir}/train.jsonl")


def cmd_im_import(args: argparse.Namespace) -> None:
    cfg, scenes, store = _ctx()
    sel_ids = list(cfg.get("user.scenes", [])) or list(scenes.keys())
    text = open(args.file, encoding="utf-8", errors="ignore").read()  # noqa: SIM115
    llm = None
    if not args.no_llm:
        try:
            llm = LLMClient.from_config(cfg)
        except Exception:  # noqa: BLE001
            llm = None
    summary = run_pipeline(
        text, args.me.split(","), cfg, scenes, sel_ids, store, llm
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("👉 所有样本为 pending 状态，请用 Streamlit 审核面板确认：streamlit run app/Home.py")


def cmd_import_answers(args: argparse.Namespace) -> None:
    cfg, scenes, store = _ctx()
    path = Path(args.file)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv_mod.DictReader(f))
        summary = import_csv_rows(store, rows, scenes, cfg.user_name)
    else:
        doc = json.loads(path.read_text(encoding="utf-8"))
        summary = import_answers(store, doc, scenes, cfg.user_name)
    print(json.dumps(summary, ensure_ascii=False))
    print("✅ 已导入问卷样本（网页版 answers.json / 已填 CSV，可在审核面板查看）")


def main() -> None:
    parser = argparse.ArgumentParser(prog="persona_lora", description="个人风格 LoRA 工作流")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("stats", help="查看数据集统计与场景缺口")
    sub.add_parser("export", help="导出 train/validation jsonl")

    p_im = sub.add_parser("im-import", help="IM 聊天记录批量抽取")
    p_im.add_argument("--file", required=True, help="聊天记录 txt 路径")
    p_im.add_argument("--me", required=True, help="你的昵称（多个逗号分隔）")
    p_im.add_argument("--no-llm", action="store_true", help="跳过 LLM 质检（纯规则模式）")

    p_ia = sub.add_parser("import-answers", help="导入网页版答卷（answers.json 或已填 CSV）")
    p_ia.add_argument("--file", required=True, help="answers.json 或 CSV 路径")

    args = parser.parse_args()
    handlers = {
        "stats": cmd_stats,
        "export": cmd_export,
        "im-import": cmd_im_import,
        "import-answers": cmd_import_answers,
    }
    handlers[args.cmd](args)


if __name__ == "__main__":
    main()
