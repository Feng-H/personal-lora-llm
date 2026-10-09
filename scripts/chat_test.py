#!/usr/bin/env python3
"""本地风格模型对话测试（走 Ollama OpenAI 兼容接口）。

用法：
    python scripts/chat_test.py                     # 默认模型 my-persona
    python scripts/chat_test.py --model my-persona --base-url http://localhost:11434/v1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from persona_lora.llm import LLMClient  # pyright: ignore[reportMissingImports]

SYSTEM = (
    "你是用户本人的数字分身，已经完全学会了TA的说话风格。"
    "请用你自己的口吻、语气词、标点习惯和句式风格自然回复，"
    "像一个真实的人那样聊天，不要AI腔，不要过度热情，不要使用列表和标题。"
)


def main() -> None:
    parser = argparse.ArgumentParser(description="风格模型本地对话测试")
    parser.add_argument("--model", default="my-persona")
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--api-key", default="ollama")
    args = parser.parse_args()

    client = LLMClient(
        base_url=args.base_url, model=args.model, api_key=args.api_key, temperature=0.8
    )
    history: list[dict] = [{"role": "system", "content": SYSTEM}]
    print(f"🧬 你的数字分身已上线（{args.model}）。输入 exit 退出，multi 开启多轮。\n")
    multi = True
    while True:
        try:
            user = input("你： ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break
        if not user:
            continue
        if user.lower() in ("exit", "quit", "退出"):
            break
        if user.lower() == "multi":
            multi = not multi
            print(f"（多轮上下文：{'开' if multi else '关'}）")
            continue
        history.append({"role": "user", "content": user})
        try:
            reply = client.chat(history if multi else history[-1:], temperature=0.8, max_tokens=300)
        except Exception as e:  # noqa: BLE001
            print(f"⚠️ 调用失败：{e}")
            continue
        print(f"\n分身： {reply}\n")
        history.append({"role": "assistant", "content": reply})


if __name__ == "__main__":
    main()
