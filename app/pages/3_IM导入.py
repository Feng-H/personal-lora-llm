"""方案三：IM 历史聊天记录智能抽取（存量批量扩容）。"""
from __future__ import annotations

from collections import Counter

import streamlit as st  # pyright: ignore[reportMissingImports]
import pandas as pd  # pyright: ignore[reportMissingImports]
from persona_lora import im_import  # pyright: ignore[reportMissingImports]
from common import get_cfg, get_llm, get_scenes, get_store

st.set_page_config(page_title="IM 历史抽取", page_icon="📥")

cfg = get_cfg()
scenes = get_scenes()
store = get_store()

st.title("📥 IM 历史聊天记录智能抽取")
st.caption(
    "本地解析 → 4-8 轮主题切片 → 本地向量场景检索 → LLM 质检标记 → 人工审核。"
    "全程私有，不上传任何聊天内容。（RAG 仅用于数据预处理，推理阶段无检索）"
)

st.warning(
    "请使用官方/合规方式自行导出私聊文本（如微信聊天记录导出工具的 txt）。"
    "本项目不提供任何 IM 逆向破解或抓取代码。",
    icon="⚠️",
)

uploaded = st.file_uploader("上传聊天记录 txt 文件", type=["txt"])
pasted = st.text_area("或直接粘贴聊天内容", height=150, placeholder="张三 2024-05-01 10:23:45\n这周末有空吗？")
text = ""
if uploaded is not None:
    text = uploaded.getvalue().decode("utf-8", errors="ignore")
elif pasted.strip():
    text = pasted

my_names_raw = st.text_input(
    "你在聊天里的昵称（多个用逗号分隔，用于角色绑定：你的发言 = assistant 原文）",
    value=cfg.user_name,
    placeholder="例如：老王, Wang, A Wang",
)

with st.expander("高级参数"):
    c1, c2, c3 = st.columns(3)
    gap = c1.number_input("对话切分间隔（分钟）", 10, 240, int(cfg.get("im_import.time_gap_minutes", 30)))
    min_r = c2.number_input("窗口最少消息数", 2, 10, int(cfg.get("im_import.min_rounds", 4)))
    max_r = c3.number_input("窗口最多消息数", 4, 20, int(cfg.get("im_import.max_rounds", 8)))
    use_llm = st.checkbox("启用本地 LLM 质检标记（推荐，需 Ollama 在线）", value=True)

raw: str = text if isinstance(text, str) else ""
if not raw.strip():
    st.info("👆 上传文件或粘贴内容后开始。")
    st.stop()

my_names = [n.strip() for n in my_names_raw.split(",") if n.strip()]
if not my_names:
    st.error("必须填写你的昵称，否则无法绑定角色（对方=user / 你=assistant）")
    st.stop()

# ---------------- 解析预览 ----------------
st.divider()
st.subheader("① 解析预览")
msgs = im_import.parse_chat_lines(raw, my_names)
if not msgs:
    st.error("没有解析出任何消息。请检查格式（支持「名字 时间+消息」/「名字: 消息」等常见导出格式）")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("解析消息数", len(msgs))
c2.metric("你的消息", len([m for m in msgs if m.is_me]))
c3.metric("对方消息", len([m for m in msgs if not m.is_me]))

speaker_counts = Counter(m.speaker for m in msgs).most_common(10)
st.dataframe(
    pd.DataFrame(speaker_counts, columns=["说话人", "消息数"]),
    use_container_width=True,
    hide_index=True,
)
st.caption("确认「你的消息」数量是否正确；不正确请调整昵称拼写。")

with st.expander("查看前 10 条解析结果"):
    for m in msgs[:10]:
        who = "🧑 我" if m.is_me else f"👤 {m.speaker}"
        st.markdown(f"**{who}**：{m.text}")

# ---------------- 运行流水线 ----------------
st.subheader("② 运行抽取流水线")
selected = [s for s in cfg.get("user.scenes", []) if s in scenes]
if not selected:
    st.warning("请先回到首页勾选要抽取的场景")
    st.stop()
st.caption("将按场景关键词向量检索，只保留匹配勾选场景的片段：" + "、".join(scenes[s].name for s in selected))

if st.button("🚀 开始抽取（首次运行会下载本地向量模型，约 100MB）", type="primary"):
    cfg.set("im_import.time_gap_minutes", int(gap))
    cfg.set("im_import.min_rounds", int(min_r))
    cfg.set("im_import.max_rounds", int(max_r))
    llm = get_llm() if use_llm else None
    status = st.status("抽取流水线运行中……", expanded=True)
    progress_holder = status.empty()

    def _progress(stage: str, done: int, total: int) -> None:
        progress_holder.write(f"{stage}：{done} / {total}")

    summary: dict = {}
    try:
        summary = im_import.run_pipeline(raw, my_names, cfg, scenes, selected, store, llm, _progress)
    except Exception as e:  # noqa: BLE001 —— 给用户完整错误上下文
        status.update(label="抽取失败", state="error", expanded=True)
        st.error(f"流水线异常：{e}")
        st.stop()
    status.update(label="抽取完成", state="complete", expanded=False)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("解析消息", summary["parsed"])
    c2.metric("主题窗口", summary["windows"])
    c3.metric("场景命中", summary["kept"])
    c4.metric("待审核样本", summary["samples"])
    st.success("已全部进入「数据审核」面板（IM 抽取样本必须人工确认后才会计入训练集）")
    st.page_link("pages/4_数据审核.py", label="🔍 去人工审核", icon="🔍")
