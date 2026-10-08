#!/usr/bin/env bash
# Mac MLX 转换：把 Kaggle 下载的 merged 16bit 模型转成 MLX 4bit（M1 8G 可流畅运行）
#
# 用法:
#   ./scripts/mlx_convert.sh <merged_hf_dir> <out_dir> [q_bits]
#   ./scripts/mlx_convert.sh persona_merged persona-mlx 4
#
# 前置: pip install mlx-lm
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "用法: $0 <merged_hf_dir> <out_dir> [q_bits=4]"
  exit 1
fi

SRC="$1"; OUT="$2"; QBITS="${3:-4}"

if [ ! -d "$SRC" ]; then
  echo "❌ 找不到目录: $SRC（请先从 Kaggle 下载 persona_merged 并解压）"
  exit 1
fi

echo "🚚 转换 $SRC → $OUT (4bit, q_bits=$QBITS) ..."
if command -v mlx_lm.convert >/dev/null 2>&1; then
  mlx_lm.convert --hf-path "$SRC" --mlx-path "$OUT" --quantize --q-bits "$QBITS"
elif python3 -m mlx_lm convert --help >/dev/null 2>&1; then
  python3 -m mlx_lm convert --hf-path "$SRC" --mlx-path "$OUT" --quantize -q
else
  echo "❌ 未安装 mlx-lm：pip install mlx-lm"
  exit 1
fi

echo ""
echo "✅ 完成。测试运行:"
echo "  python3 -m mlx_lm generate --model $OUT --prompt '这周末有空吗？出来吃个饭呗'"
