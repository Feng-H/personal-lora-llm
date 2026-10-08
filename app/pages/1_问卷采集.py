"""方案一：场景化问卷快速冷启动（支持网页版答卷/已填 CSV 回流导入）。"""
from __future__ import annotations

import csv
import io
import json

import streamlit as st  # pyright: ignore[reportMissingImports]
from persona_lora import questionnaire  # pyright: ignore[reportMissingImports]
from common import get_cfg, get_scenes, get_store

st.set_page_config(page_title="问卷采集", page_icon="📝")

cfg = get_cfg()
scenes = get_scenes()
store = get_store()

st.title("📝 场景化问卷冷启动")
st.caption("全部为真实场景问答对：别人会怎么问 / 你会怎么答。用你平时的口吻，别润色。")

selected = [s for s in cfg.get("user.scenes", []) if s in scenes]
if not selected:
    st.warning("请先回到首页勾选要复刻的场景")
    st.stop()

scene = st.selectbox(
    "采集场景",
    selected,
    format_func=lambda sid: f"{scenes[sid].icon} {scenes[sid].name}",
)
if not isinstance(scene, str) or scene not in scenes:
    st.stop()
scene_obj = scenes[scene]
bank = questionnaire.load_bank(scene_obj)
if not bank:
    st.error(f"题库缺失：{scene_obj.questionnaire_path}")
    st.stop()

answered = questionnaire.answered_qids(store, scene)
done = len([b for b in bank if questionnaire.qid(scene, b["idx"]) in answered])
st.progress(
    done / len(bank) if bank else 1.0,
    text=f"已完成 {done} / {len(bank)} 题（每题 = 1 条训练样本）",
)

remaining = [b["idx"] for b in bank if questionnaire.qid(scene, b["idx"]) not in answered]

# ---------------- 导入回流：网页版答卷 / 已填 CSV ----------------
with st.expander("📥 导入：网页版答卷 answers.json / 已填 CSV（不想逐题填？用这个）"):
    st.caption(
        "推荐用手机打开网页版问卷（零安装）：仓库主页 → 在线问卷；填完下载 answers.json 回传这里，"
        "或下载空白 CSV 用 Excel 填。导入后仍可在下方逐题补答。"
    )
    f_json = st.file_uploader("answers.json（网页版导出）", type=["json"], key="up_answers")
    f_csv = st.file_uploader("已填 CSV（网页模板 / Excel 另存 CSV UTF-8）", type=["csv"], key="up_csv")
    if f_json is not None:
        try:
            doc = json.loads(f_json.getvalue().decode("utf-8"))
            summary = questionnaire.import_answers(store, doc, scenes, cfg.user_name)
        except Exception as e:  # noqa: BLE001
            st.error(f"导入失败：{e}")
        else:
            st.toast(f"已导入 {summary['added']} 条，跳过（已答/无效）{summary['skipped']} 条")
            st.rerun()
    if f_csv is not None:
        try:
            rows = list(csv.DictReader(io.StringIO(f_csv.getvalue().decode("utf-8-sig"))))
            summary = questionnaire.import_csv_rows(store, rows, scenes, cfg.user_name)
        except Exception as e:  # noqa: BLE001
            st.error(f"导入失败：{e}")
        else:
            st.toast(f"已导入 {summary['added']} 条，跳过（已答/无效）{summary['skipped']} 条")
            st.rerun()

if not remaining:
    st.balloons()
    st.success("该场景题库已全部完成 🎉 建议：「对话采集」继续自然积累，或「IM 导入」批量扩容。")
    st.stop()

# 跳过机制：session_state 记住跳过的题
skipped = set(st.session_state.get("skipped", []))
todo = [i for i in remaining if i not in skipped]
if not todo:
    st.info("剩余题目均已跳过。重置跳过：")
    if st.button("重置跳过的题目"):
        st.session_state["skipped"] = []
        st.rerun()
    st.stop()

item = next(b for b in bank if b["idx"] == todo[0])

st.divider()
c1, c2 = st.columns([1, 4])
c1.markdown(f"### 第 {item['idx'] + 1} 题")
if item["context"]:
    c2.markdown(f"**📍 情境**：{item['context']}")
st.markdown("💬 **对方说**：")
st.info(item["question"], icon="🗣️")

answer = st.text_area(
    "✍️ 你会怎么回？（语气词、标点、换行全保留，想怎么打字就怎么打）",
    height=130,
    placeholder="例如：这需求有点赶啊……我先看看能不能插进去，明天给你答复行不",
)

b1, b2, _ = st.columns([1, 1, 3])
if b1.button("✅ 保存这条", type="primary", disabled=not answer.strip()):
    sample = questionnaire.make_sample(scene_obj, cfg.user_name, item, answer)
    if sample is None:
        st.error("回答内容为空或纯噪声，没有入库。写点真实的呗～")
    else:
        store.add(sample)
        if "风险" in sample["flags"]:
            st.warning("已保存（含隐私内容已自动打码，审核面板可复核）")
        else:
            st.toast("已入库 1 条样本 ✅")
        st.rerun()
if b2.button("⏭️ 跳过"):
    st.session_state.setdefault("skipped", set()).add(item["idx"])
    st.rerun()
