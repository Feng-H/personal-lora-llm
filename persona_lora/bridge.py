"""外部 Agent 宿主桥接（OpenClaw / Hermes 等）。

宿主通过 shell 调用本模块，把用户消息送入采集 Agent 并拿回 JSON：

    python -m persona_lora.bridge --session openclaw --message "最近好忙啊"
    → {"reply": "...", "proactive": null}

    python -m persona_lora.bridge --session openclaw --poll-proactive   # 空闲轮询
    python -m persona_lora.bridge --session openclaw --close            # 结束封存
    python -m persona_lora.bridge --session openclaw --note-ignore      # 用户无视主动话题
"""
from __future__ import annotations

import argparse
import json

from .agent_chat import PersonaCollector
from .config import load_config
from .llm import LLMClient
from .scenes import load_scenes
from .store import SampleStore


def _collector() -> PersonaCollector:
    cfg = load_config()
    scenes = load_scenes()
    store = SampleStore(cfg.samples_file)
    try:
        llm = LLMClient.from_config(cfg)
    except Exception:  # noqa: BLE001 —— 无 LLM 也可降级采集
        llm = None
    return PersonaCollector(cfg, store, scenes, llm)


def main() -> None:
    parser = argparse.ArgumentParser(description="persona_lora 对话采集桥接")
    parser.add_argument("--session", required=True, help="会话 id（宿主自定，如 openclaw）")
    parser.add_argument("--message", help="用户消息原文")
    parser.add_argument("--scene", help="新会话场景 id（可选）")
    parser.add_argument("--poll-proactive", action="store_true", help="空闲主动搭话轮询")
    parser.add_argument("--close", action="store_true", help="结束会话并封存样本")
    parser.add_argument("--note-ignore", action="store_true", help="用户无视了主动话题")
    args = parser.parse_args()

    collector = _collector()
    session = collector.load_session(args.session)
    if session is None:
        created = collector.new_session(args.scene or collector._default_scene_id())  # noqa: SLF001
        orphan = collector._session_path(created["id"])  # noqa: SLF001
        created["id"] = args.session  # 使用宿主指定的稳定会话 id
        collector.save_session(created)
        orphan.unlink(missing_ok=True)
        session = created

    if args.close:
        n = collector.close_session(args.session)
        print(json.dumps({"closed": True, "assistant_turns": n}, ensure_ascii=False))
        return
    if args.note_ignore:
        session_now = collector.load_session(args.session)
        if session_now is not None:
            collector.engine.note_ignore(session_now)
            collector.save_session(session_now)
        print(json.dumps({"noted": "ignore"}, ensure_ascii=False))
        return
    if args.poll_proactive:
        msg = collector.standalone_proactive(args.session)
        print(json.dumps({"proactive": msg}, ensure_ascii=False))
        return
    if args.message:
        result = collector.reply(args.session, args.message)
        print(json.dumps(result, ensure_ascii=False))
        return
    print(json.dumps({"error": "no action"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
