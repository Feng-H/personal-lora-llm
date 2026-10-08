#!/usr/bin/env bash
# Kaggle Notebook 与 GitHub 仓库双向同步
#
# 用法：
#   ./scripts/sync_kaggle.sh check              # 本地校验（无需 Kaggle token）
#   ./scripts/sync_kaggle.sh push               # 仓库 notebook → Kaggle（自动配好 GPU/Internet/数据集）
#   ./scripts/sync_kaggle.sh push --no-dataset  # 推送但不预挂数据集（手动在 UI 挂）
#   ./scripts/sync_kaggle.sh pull               # Kaggle → notebooks/.kaggle_pull/（查看改动）
#   ./scripts/sync_kaggle.sh pull --apply       # Kaggle → 覆盖仓库 notebook（回写改动）
#
# 一次性准备（仅需做一次）：
#   1. 打开 https://www.kaggle.com/settings → API → Create New Token（下载 kaggle.json）
#   2. mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
META="$REPO/notebooks/kernel-metadata.json"
NB="$REPO/notebooks/kaggle_persona_lora.ipynb"
PULL_DIR="$REPO/notebooks/.kaggle_pull"

# kaggle CLI：优先项目 venv
KAGGLE="$REPO/.venv/bin/kaggle"
[ -x "$KAGGLE" ] || KAGGLE="$(command -v kaggle || true)"

say() { printf "%s\n" "$*"; }
die() { printf "❌ %s\n" "$*" >&2; exit 1; }

kernel_slug() {  # 从 metadata 读 id，去掉用户名前缀
  python3 - "$META" <<'PY'
import json, sys
meta = json.load(open(sys.argv[1], encoding="utf-8"))
print(meta["id"].split("/", 1)[-1])
PY
}

require_token() {
  [ -f "$HOME/.kaggle/kaggle.json" ] || die "未找到 ~/.kaggle/kaggle.json
   一次性准备：https://www.kaggle.com/settings → API → Create New Token
   然后：mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json"
  [ -n "$KAGGLE" ] || die "kaggle CLI 不可用：pip install kaggle（项目 venv 已含）"
}

kaggle_username() {
  python3 -c "import json;print(json.load(open('$HOME/.kaggle/kaggle.json'))['username'])"
}

check_mode() {
  python3 - "$META" "$NB" <<'PY'
import json, sys
meta_path, nb_path = sys.argv[1], sys.argv[2]
try:
    meta = json.load(open(meta_path, encoding="utf-8"))
except Exception as e:
    print(f"❌ kernel-metadata.json 解析失败：{e}"); sys.exit(1)
import os
if not os.path.exists(nb_path):
    print(f"❌ 缺少 notebook：{nb_path}"); sys.exit(1)
problems = []
if "__KAGGLE_USERNAME__" in meta["id"]:
    print("ℹ️  id 含占位符，push 时会用 ~/.kaggle/kaggle.json 的用户名自动替换")
if meta.get("dataset_sources") and any("__KAGGLE_USERNAME__" in d for d in meta["dataset_sources"]):
    print("ℹ️  dataset_sources 含占位符，push 时自动替换；数据集不存在则自动改为不挂载并提示")
print("✅ 元数据与 notebook 就绪：")
print(f"   kernel: {meta['id']}  (private={meta.get('is_private')}, gpu={meta.get('enable_gpu')}, internet={meta.get('enable_internet')})")
print(f"   notebook: {os.path.basename(nb_path)}")
for d in meta.get("dataset_sources", []):
    print(f"   dataset: {d}")
PY
}

push_mode() {
  require_token
  USER="$(kaggle_username)"
  BUILD="$(mktemp -d)"
  trap 'rm -rf "$BUILD"' EXIT
  python3 - "$META" "$BUILD/kernel-metadata.json" "$USER" "$NB" "${1:-}" <<'PY'
import json
import os
import shutil
import sys

src, dst, user, nb, dataset_flag = sys.argv[1:6]
meta = json.load(open(src, encoding="utf-8"))
meta["id"] = meta["id"].replace("__KAGGLE_USERNAME__", user)
meta["dataset_sources"] = [d.replace("__KAGGLE_USERNAME__", user) for d in meta.get("dataset_sources", [])]
if dataset_flag == "--no-dataset":
    meta["dataset_sources"] = []
os.makedirs(os.path.dirname(dst), exist_ok=True)
json.dump(meta, open(dst, "w", encoding="utf-8"), indent=2)
shutil.copy(nb, os.path.join(os.path.dirname(dst), "kaggle_persona_lora.ipynb"))
print(f"kernel id → {meta['id']}")
PY
  say "→ 推送到 Kaggle：$(kernel_slug)"
  if ! out="$("$KAGGLE" kernels push -p "$BUILD" 2>&1)"; then
    if echo "$out" | grep -qi "dataset\|404\|not found"; then
      say "⚠️  数据集挂载失败（还没上传数据集？），改为不挂载重试……"
      python3 -c "
import json
p = '$BUILD/kernel-metadata.json'
m = json.load(open(p)); m['dataset_sources'] = []
json.dump(m, open(p, 'w'), indent=2)"
      out="$("$KAGGLE" kernels push -p "$BUILD" 2>&1)" || die "推送失败：$out
   训练前请在 Kaggle UI 右侧 Add Input 手动挂载数据集"
      say "$out"
      say "✅ 已推送（未挂数据集）。→ https://www.kaggle.com/code/$USER/$(kernel_slug)"
      exit 0
    fi
    die "推送失败：$out"
  fi
  say "$out"
  say "✅ 已推送。→ https://www.kaggle.com/code/$USER/$(kernel_slug)"
  say "   数据集已按 metadata 预挂；GPU/Internet 已启用，直接 Run All 即可。"
}

pull_mode() {
  require_token
  USER="$(kaggle_username)"
  SLUG="$(kernel_slug)"
  mkdir -p "$PULL_DIR"
  say "→ 从 Kaggle 拉取 $USER/$SLUG ……"
  "$KAGGLE" kernels pull "$USER/$SLUG" -p "$PULL_DIR" || die "拉取失败（kernel 是否已 push 过？）"
  if [ "${1:-}" = "--apply" ]; then
    cp "$PULL_DIR/kaggle_persona_lora.ipynb" "$NB"
    say "✅ 已回写仓库 notebook：$NB（记得 git commit）"
  else
    say "✅ 已拉取到 $PULL_DIR（对比确认后用 --apply 回写仓库）"
    command -v diff >/dev/null && diff -q "$PULL_DIR/kaggle_persona_lora.ipynb" "$NB" >/dev/null 2>&1 \
      && say "（与仓库版本一致，无差异）" || true
  fi
}

case "${1:-check}" in
  check) check_mode ;;
  push)  push_mode "${2:-}" ;;
  pull)  pull_mode "${2:-}" ;;
  *)     die "用法：$0 check | push [--no-dataset] | pull [--apply]" ;;
esac
