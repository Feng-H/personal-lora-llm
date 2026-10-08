"""导出训练集 & Kaggle 训练指引。"""
from __future__ import annotations

from pathlib import Path

import pandas as pd  # pyright: ignore[reportMissingImports]
import streamlit as st  # pyright: ignore[reportMissingImports]
from persona_lora import export as export_mod  # pyright: ignore[reportMissingImports]
from persona_lora.scenes import selected_scenes  # pyright: ignore[reportMissingImports]
from persona_lora.stats import scene_gaps  # pyright: ignore[reportMissingImports]
from common import fresh_stats, get_cfg, get_scenes, get_store

st.set_page_config(page_title="导出训练", page_icon="🚀")

cfg = get_cfg()
scenes = get_scenes()
store = get_store()

st.title("🚀 导出训练集 → Kaggle 一键训练")
st.caption("统一输出 Qwen messages jsonl（train / validation），配合仓库内置 Unsloth Notebook 训练。")

stats = fresh_stats()
basic = int(cfg.get("collector.basic_target", 70))
optimal = int(cfg.get("collector.optimal_target", 120))
multi = cfg.get("user.mode", "single") == "multi"
sel = selected_scenes(cfg, scenes)


def do_export(min_total: int) -> None:
    try:
        card = export_mod.export_dataset(
            store.all(), scenes, sel, cfg, cfg.exports_dir, multi, min_total=min_total
        )
    except export_mod.ExportError as e:
        st.error(str(e))
        return
    st.success(
        f"导出成功：train {card['train_samples']} 条 / validation {card['validation_samples']} 条"
    )
    out: Path = cfg.exports_dir
    train_bytes = (out / "train.jsonl").read_bytes()
    c1, c2 = st.columns(2)
    c1.download_button("⬇️ 下载 train.jsonl", train_bytes, "train.jsonl", "application/jsonl")
    val_path = out / "validation.jsonl"
    if val_path.exists():
        c2.download_button(
            "⬇️ 下载 validation.jsonl", val_path.read_bytes(), "validation.jsonl", "application/jsonl"
        )


# ---------------- 就绪检查 ----------------
st.subheader("训练就绪检查")
r1 = stats["total"] >= basic
r2 = stats["total"] >= optimal
c1, c2 = st.columns(2)
c1.metric("总有效样本", stats["total"],
          delta="≥ 基础线" if r1 else f"还差 {basic - stats['total']} 条",
          delta_color="normal" if r1 else "inverse")
c2.metric("状态", "✅ 最优体量" if r2 else ("🟡 基础可用" if r1 else "⏳ 未达标"))

gaps = scene_gaps(stats, scenes, [s.id for s in sel], multi)
st.dataframe(
    pd.DataFrame(gaps).rename(
        columns={"name": "场景", "have": "已有", "need": "目标", "gap": "缺口", "ratio": "达成率"}
    ),
    use_container_width=True,
    hide_index=True,
)
if multi:
    weak = [g for g in gaps if g["gap"] > 0]
    if weak:
        st.error(
            "多场景模式强制校验：以下场景样本不足，导出将被拦截（防止风格混杂）——"
            + "、".join(f"{g['name']} 缺 {g['gap']}" for g in weak)
        )
    else:
        st.success("多场景校验通过：所有勾选场景均达标 ✅")

with st.expander("🧪 试导出（跑通流程用，忽略最低样本阈值）"):
    st.caption("仅用于验证 Kaggle 流水线；正式训练请回到 70+ 条。")
    if st.button("生成试导出数据集（min_total=10）"):
        do_export(min_total=10)

# ---------------- 导出 ----------------
st.divider()
if st.button("📦 生成训练集", type="primary", disabled=not r1):
    do_export(min_total=basic)

# ---------------- Kaggle 指引 ----------------
st.divider()
st.subheader("Kaggle 一键训练（免费 T4 · 2-3 小时）")
steps = """
1. **Fork/下载本仓库**，拿到 `notebooks/kaggle_persona_lora.ipynb`
2. **上传数据集**：Kaggle 网页 → Datasets → New Dataset → 上传 `train.jsonl` + `validation.jsonl`（私有）
3. **新建 Notebook**：上传 ipynb，右侧 Add Input → 添加你刚建的数据集；Settings 打开 Internet 与 GPU T4
4. **Run All**：预置最优超参（Unsloth 4bit / LoRA r=16 / epoch 3 / lr 2e-4），无需调参
5. **下载产物**：训练完成自动输出 `lora_adapter.zip`（几十 MB）与可选 GGUF
"""
st.markdown(steps)
st.info("详细图文与常见问题见 `docs/kaggle_guide.md`；本地部署（Ollama / MLX）见 `docs/hardware.md`")
