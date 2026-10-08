#!/usr/bin/env python3
"""生成 Ollama Modelfile 并给出创建命令（ChatML 模板，适配 Qwen 系列）。

用法：
    python scripts/make_ollama.py --gguf persona_gguf/unsloth.Q4_K_M.gguf --name my-persona
    # 然后执行输出的一行命令：ollama create my-persona -f Modelfile.persona
"""
from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_SYSTEM = (
    "你是用户本人的数字分身，已经完全学会了TA的说话风格。"
    "请用你自己的口吻、语气词、标点习惯和句式风格自然回复，"
    "像一个真实的人那样聊天，不要AI腔，不要过度热情，不要使用列表和标题。"
)

CHATML_TEMPLATE = '''TEMPLATE """{{- if .System }}<|im_start|>system
{{ .System }}<|im_end|>
{{ end }}{{- range .Messages }}<|im_start|>{{ .Role }}
{{ .Content }}<|im_end|>
{{ end }}<|im_start|>assistant
"""'''


def main() -> None:
    parser = argparse.ArgumentParser(description="生成 Ollama Modelfile")
    parser.add_argument("--gguf", required=True, help="GGUF 模型文件路径")
    parser.add_argument("--name", default="my-persona", help="Ollama 模型名")
    parser.add_argument("--system", default=DEFAULT_SYSTEM, help="系统提示词")
    parser.add_argument("--ctx", type=int, default=4096, help="上下文长度")
    args = parser.parse_args()

    gguf = Path(args.gguf).resolve()
    if not gguf.exists():
        raise SystemExit(f"❌ 找不到 GGUF：{gguf}")

    modelfile = f'''FROM {gguf}

{CHATML_TEMPLATE}

PARAMETER stop "<|im_start|>"
PARAMETER stop "<|im_end|>"
PARAMETER num_ctx {args.ctx}
PARAMETER temperature 0.8

SYSTEM \"\"\"{args.system}\"\"\"
'''
    out = Path("Modelfile.persona")
    out.write_text(modelfile, encoding="utf-8")
    print(f"✅ 已生成 {out.resolve()}")
    print(f"\n下一步：\n  ollama create {args.name} -f {out}\n  ollama run {args.name}\n")


if __name__ == "__main__":
    main()
