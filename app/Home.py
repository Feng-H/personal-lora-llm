"""个人风格 LoRA 工作台首页：总览 + 场景配置 + 采集进度仪表盘。"""
from __future__ import annotations

import streamlit as st  # pyright: ignore[reportMissingImports]

from common import fresh_stats, get_cfg, get_scenes, llm_status, save_user_settings

st.set_page_config(page_title="风格 LoRA 工作台", page_icon="🧬", layout="wide")

cfg = get_cfg()
scenes = get_scenes()

# ---------------- 侧边栏：用户设置 ----------------
with st.sidebar:
    st.header("🧬 我的风格分身")
    name = st.text_input("你的昵称（用于系统提示词）", value=cfg.user_name, max_chars=20)
    mode = st.radio(
        "采集模式",
        ["single", "multi"],
        format_func=lambda x: "单场景专精（推荐）" if x == "single" else "多场景全能",
        index=0 if cfg.get("user.mode", "single") == "single" else 1,
    )
    current = list(cfg.get("user.scenes", []) or [])
    scene_ids = st.multiselect(
        "勾选要复刻的风格场景",
        options=list(scenes.keys()),
        default=[s for s in current if s in scenes],
        format_func=lambda sid: f"{scenes[sid].icon} {scenes[sid].name}",
    )
    if st.button("保存设置", type="primary", use_container_width=True):
        if mode == "multi" and len(scene_ids) < 2:
            st.error("多场景模式至少勾选 2 个场景")
        elif not scene_ids:
            st.error("至少勾选 1 个场景")
        else:
            save_user_settings(name, mode, scene_ids)
            st.success("已保存")
    st.divider()
    ok, model = llm_status()
    st.caption(f"本地 LLM：{'✅ ' + model if ok else '⚠️ 不可用（' + model + '）'}")
    st.caption("配置 Ollama 后自动启用：`ollama serve` + `ollama pull qwen3:8b`")

# ---------------- 主区：总览 ----------------
st.title("🧬 个人真实风格 AI-LoRA 全自动复刻系统")
st.caption(
    "问卷冷启动 + AI 双向对话积累 + IM 历史抽取 → 本地清洗质检 → Kaggle Unsloth 训练 → 纯 LoRA 推理"
)

stats = fresh_stats()
basic = int(cfg.get("collector.basic_target", 70))
optimal = int(cfg.get("collector.optimal_target", 120))

c1, c2, c3, c4 = st.columns(4)
c1.metric("有效样本", stats["total"], f"基础线 {basic}")
c2.metric("待人工审核", stats["pending_review"])
c3.metric("平均回复长度", f"{stats['quality']['avg_assistant_len']} 字")
c4.metric(
    "训练就绪",
    "✅ 最优" if stats["total"] >= optimal else ("🟡 基础" if stats["total"] >= basic else "⏳ 采集中"),
)

st.subheader("采集进度")
p = st.progress(
    min(1.0, stats["total"] / optimal),
    text=f"总样本 {stats['total']} / 最优目标 {optimal}（基础线 {basic}）",
)
if stats["total"] >= optimal:
    p.success("已达最优体量：主动采集自动关闭，可以导出训练了！")

st.subheader("三通道数据采集")
g1, g2, g3 = st.columns(3)
g1.page_link("pages/1_问卷采集.py", label="📝 问卷冷启动", icon="📝")
g1.caption(f"已贡献 {stats['by_source']['questionnaire']} 条 · 极速打底")
g2.page_link("pages/2_对话采集.py", label="💬 双向对话采集", icon="💬")
g2.caption(f"已贡献 {stats['by_source']['agent_chat']} 条 · 主动补齐王牌")
g3.page_link("pages/3_IM导入.py", label="📥 IM 历史抽取", icon="📥")
g3.caption(f"已贡献 {stats['by_source']['im_import']} 条 · 存量复用")

st.subheader("场景样本分布")
if not stats["by_scene"]:
    st.info("先在左侧勾选场景，再开始采集。")
else:
    multi = cfg.get("user.mode", "single") == "multi"
    for sid, info in stats["by_scene"].items():
        have = info["count"]
        target = scenes[sid].min_samples(multi) if sid in scenes else basic
        st.progress(
            min(1.0, have / target if target else 1.0),
            text=f"{scenes[sid].icon if sid in scenes else '🏷️'} {info['name']}：{have} / {target}",
        )

with st.expander("质检指标（结构缺陷检测输入）"):
    q = stats["quality"]
    st.json(
        {
            "敷衍短句占比": q["short_reply_ratio"],
            "多轮样本占比": q["multi_turn_ratio"],
            "平均 assistant 长度": q["avg_assistant_len"],
        }
    )

st.divider()
c1, c2 = st.columns(2)
c1.page_link("pages/4_数据审核.py", label="🔍 数据审核面板", icon="🔍")
c2.page_link("pages/5_导出训练.py", label="🚀 导出训练集 & Kaggle", icon="🚀")
