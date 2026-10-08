"""数据审核面板：预览 / 编辑 / 通过 / 拒绝，最终决策权归用户。"""
from __future__ import annotations

import streamlit as st  # pyright: ignore[reportMissingImports]
from persona_lora.cleaning import scan_flags  # pyright: ignore[reportMissingImports]
from common import get_cfg, get_scenes, get_store

st.set_page_config(page_title="数据审核", page_icon="🔍")

cfg = get_cfg()
scenes = get_scenes()
store = get_store()

st.title("🔍 数据集审核面板")
st.caption("机器只做标记，所有最终决策权归你。IM 抽取样本必须在此确认后才计入训练集。")

samples = store.all()
if not samples:
    st.info("还没有任何样本。先去「问卷采集」或「对话采集」吧。")
    st.stop()

# ---------------- 过滤器 ----------------
c1, c2, c3, c4 = st.columns(4)
source_f = c1.selectbox(
    "来源",
    ["全部", "questionnaire", "agent_chat", "im_import"],
    format_func=lambda x: {"全部": "全部", "questionnaire": "📝 问卷",
                           "agent_chat": "💬 对话", "im_import": "📥 IM 抽取"}.get(x) or str(x),
)
scene_f = c2.selectbox(
    "场景", ["全部"] + list(scenes.keys()),
    format_func=lambda x: "全部" if x == "全部" else scenes[x].name,
)
status_f = c3.selectbox("状态", ["全部", "approved", "pending", "rejected"])
flag_f = c4.selectbox("标记", ["全部", "风险", "低质量", "人工复核", "场景错配", "无标记"])


def _match(s: dict) -> bool:
    if source_f != "全部" and s.get("source") != source_f:
        return False
    if scene_f != "全部" and s.get("scene") != scene_f:
        return False
    if status_f != "全部" and s.get("status") != status_f:
        return False
    if flag_f == "无标记":
        return not s.get("flags")
    return flag_f == "全部" or flag_f in s.get("flags", [])


filtered = [s for s in samples if _match(s)]
st.caption(f"共 {len(filtered)} / {len(samples)} 条样本")

if not filtered:
    st.stop()

# ---------------- 批量操作 ----------------
b1, b2 = st.columns([1, 1])
if b1.button("✅ 通过当前过滤的全部样本", type="primary"):
    n = 0
    for s in filtered:
        if s.get("status") != "approved":
            store.update(s["id"], status="approved")
            n += 1
    st.toast(f"已批量通过 {n} 条")
    st.rerun()
if b2.button("🚫 拒绝当前过滤的全部样本"):
    n = 0
    for s in filtered:
        if s.get("status") != "rejected":
            store.update(s["id"], status="rejected")
            n += 1
    st.toast(f"已批量拒绝 {n} 条")
    st.rerun()

# ---------------- 分页列表 ----------------
PAGE = 10
total_pages = (len(filtered) + PAGE - 1) // PAGE
if "review_page" not in st.session_state:
    st.session_state.review_page = 0
st.session_state.review_page = max(0, min(st.session_state.review_page, total_pages - 1))
p = st.radio("页码", range(total_pages), horizontal=True,
             index=st.session_state.review_page,
             label_visibility="collapsed",
             format_func=lambda i: f"{i + 1}")
st.session_state.review_page = p
page_items = filtered[p * PAGE : (p + 1) * PAGE]

SOURCE_ICON = {"questionnaire": "📝", "agent_chat": "💬", "im_import": "📥"}
FLAG_COLOR = {"风险": "🔴", "低质量": "🟡", "人工复核": "🟠", "场景错配": "🟣"}

for s in reversed(page_items):
    scene = scenes.get(s.get("scene", ""))
    head = (
        f"{SOURCE_ICON.get(s['source'], '❔')} "
        f"{scene.icon + ' ' if scene else ''}{scene.name if scene else s.get('scene')}"
        f" ｜ {s.get('status')} ｜ {s.get('created_at', '')[:16]}"
    )
    with st.expander(f"{head} ｜ {' '.join(FLAG_COLOR.get(f, '⚪') + f for f in s.get('flags', [])) or '无标记'}"):
        # 消息预览 + 编辑
        edited = []
        for i, m in enumerate(s.get("messages", [])):
            label = "🧑 user（别人/AI 采访者）" if m["role"] == "user" else "🫵 assistant（你本人原文）"
            new_text = st.text_area(label, value=m["content"], height=80,
                                    key=f"msg_{s['id']}_{i}")
            edited.append({"role": m["role"], "content": new_text})
        c1, c2, c3, c4 = st.columns(4)
        if c1.button("✅ 通过", key=f"ok_{s['id']}", type="primary"):
            store.update(s["id"], status="approved", messages=edited)
            st.toast("已通过")
            st.rerun()
        if c2.button("🚫 拒绝", key=f"no_{s['id']}"):
            store.update(s["id"], status="rejected", messages=edited)
            st.toast("已拒绝（不进入训练集）")
            st.rerun()
        if c3.button("💾 保存编辑", key=f"edit_{s['id']}"):
            new_flags = sorted(set(s.get("flags", [])) | set(scan_flags(edited)))
            store.update(s["id"], messages=edited, flags=new_flags)
            st.toast("已保存（并重跑规则质检，只加标记不删内容）")
            st.rerun()
        if c4.button("🗑️ 删除", key=f"del_{s['id']}"):
            store.delete(s["id"])
            st.toast("已删除")
            st.rerun()
        if s.get("meta", {}).get("judge_reason"):
            st.caption(f"LLM 质检意见：{s['meta']['judge_reason']}")
        if s.get("meta", {}).get("sim") is not None:
            st.caption(f"场景向量相似度：{s['meta']['sim']}")
