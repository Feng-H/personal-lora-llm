"""方案二：双向智能对话采集（被动应答 + 主动补齐）。"""
from __future__ import annotations

import json
import time

import streamlit as st  # pyright: ignore[reportMissingImports]
from persona_lora import agent_chat  # pyright: ignore[reportMissingImports]
from persona_lora.stats import scene_gaps  # pyright: ignore[reportMissingImports]
from common import fresh_stats, get_cfg, get_llm, get_scenes, get_store

st.set_page_config(page_title="对话采集", page_icon="💬")

cfg = get_cfg()
scenes = get_scenes()
store = get_store()
collector = agent_chat.PersonaCollector(cfg, store, scenes, get_llm())

st.title("💬 双向对话采集")
st.caption("像平时聊天一样说话即可。AI 扮演「别人」，你说的每句话都在沉淀你的语言人格。")

selected = [s for s in cfg.get("user.scenes", []) if s in scenes]
if not selected:
    st.warning("请先回到首页勾选场景")
    st.stop()


def start_session(scene_id: str) -> None:
    s = collector.new_session(scene_id)
    st.session_state.chat_session = s["id"]
    st.session_state.chat_scene = scene_id
    # 开场白同步进聊天性示（它正是第一条训练对的 user 侧）
    st.session_state.chat_log = [
        {"role": m["role"], "text": m["text"], "proactive": m.get("proactive", False)}
        for m in s["transcript"]
    ]


def render_log() -> None:
    for m in st.session_state.get("chat_log", []):
        if m["role"] == "human":
            with st.chat_message("user"):
                st.markdown(m["text"])
        else:
            with st.chat_message("assistant"):
                st.markdown(m["text"])
                if m.get("proactive"):
                    st.caption("🤖 主动发起（补齐薄弱场景样本）")


def try_idle_proactive(force: bool = False) -> None:
    sid = st.session_state.get("chat_session")
    if not isinstance(sid, str):
        return
    session = collector.load_session(sid)
    if session is None:
        return
    idle_min = collector._idle_minutes(session)  # noqa: SLF001
    stats = fresh_stats()
    gaps = scene_gaps(stats, scenes, list(stats["by_scene"].keys()),
                      cfg.get("user.mode", "single") == "multi")
    decision = collector.engine.evaluate(
        session, stats, gaps,
        idle_minutes_elapsed=999 if force else idle_min,
        allow_idle=True,
    )
    if not decision:
        if force:
            st.toast("当前未触发主动条件（样本达标 / 限流 / 无缺口）")
        return
    collector.engine.mark_sent(session)
    msg = collector.engine.build_message(decision, session, collector.llm)
    session["transcript"].append(
        {"role": "ai", "text": msg, "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "proactive": True}
    )
    collector.save_session(session)
    st.session_state.chat_log.append({"role": "ai", "text": msg, "proactive": True})


# ---------- 侧边栏 ----------
with st.sidebar:
    st.subheader("会话控制")
    current_sid = st.session_state.get("chat_session")
    if isinstance(current_sid, str):
        st.success(f"进行中：{current_sid}")
        if st.button("🏁 结束会话并封存样本", type="primary", use_container_width=True):
            n = collector.close_session(current_sid)
            st.session_state.chat_session = None
            st.session_state.chat_log = []
            st.toast(f"会话已封存，本会话累计 {n} 条 assistant 样本")
            st.rerun()
    else:
        scene_id = st.selectbox(
            "新会话场景",
            selected,
            format_func=lambda sid: f"{scenes[sid].icon} {scenes[sid].name}",
        )
        if (
            st.button("🆕 开始新会话", type="primary", use_container_width=True)
            and isinstance(scene_id, str)
            and scene_id
        ):
            start_session(scene_id)
            st.rerun()

    st.divider()
    st.subheader("主动发起状态")
    try:
        state_json = json.loads(cfg.state_file.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        state_json = {"daily": {"date": "", "count": 0}, "permanent_passive": False}
    today = time.strftime("%Y-%m-%d")
    daily = state_json["daily"]["count"] if state_json["daily"]["date"] == today else 0
    max_day = int(cfg.get("collector.max_proactive_per_day", 3))
    st.progress(daily / max_day if max_day else 1.0, text=f"今日主动 {daily} / {max_day}")
    if state_json.get("permanent_passive"):
        st.warning("已触发防骚扰降级：永久被动模式（连续 2 次无视主动话题）")
    if st.button("🔔 戳一下（模拟空闲，让 AI 主动搭话）"):
        try_idle_proactive(force=True)
        st.rerun()

# ---------- 主区 ----------
render_log()

active_sid = st.session_state.get("chat_session")
if not isinstance(active_sid, str) or not active_sid:
    st.info("👈 在侧边栏开始一个会话，随便聊就行。AI 会在样本薄弱时自然地找你聊对应话题。")
    st.stop()

# 空闲轮询（每次交互触发检查）
try_idle_proactive(force=False)

prompt = st.chat_input("随便聊……（你的每句话都会按原文沉淀为训练样本）")
if prompt and isinstance(active_sid, str):
    st.session_state.chat_log.append({"role": "human", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner(""):
            result = collector.reply(active_sid, prompt)
        st.markdown(result["reply"])
        if result.get("proactive"):
            st.caption(f"🤖 本轮已主动补齐【{result['proactive']['scene_name']}】场景样本")
    st.session_state.chat_log.append(
        {"role": "ai", "text": result["reply"], "proactive": bool(result.get("proactive"))}
    )
    if result.get("dropped"):
        st.toast(f"本条消息含纯噪声（{result['dropped']}），未计入样本")
