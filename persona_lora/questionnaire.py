"""方案一：场景化问卷快速冷启动（全部为真实场景问答对，无抽象性格题）。"""
from __future__ import annotations

import csv

from .cleaning import clean_text
from .scenes import Scene
from .store import SampleStore, new_sample


def load_bank(scene: Scene) -> list[dict]:
    """读取场景问卷题库：[{idx, context, question}]。"""
    path = scene.questionnaire_path
    if not path.exists():
        return []
    items: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            q = (row.get("question") or "").strip()
            if not q:
                continue
            items.append(
                {"idx": i, "context": (row.get("context") or "").strip(), "question": q}
            )
    return items


def qid(scene_id: str, idx: int) -> str:
    return f"{scene_id}#{idx}"


def answered_qids(store: SampleStore, scene_id: str) -> set[str]:
    return {
        s.get("meta", {}).get("qid")
        for s in store
        if s.get("source") == "questionnaire"
        and s.get("scene") == scene_id
        and s.get("meta", {}).get("qid")
    }


def make_sample(scene: Scene, user_name: str, item: dict, answer: str) -> dict | None:
    """问卷回答 → 训练样本。用户答案仅清洗噪声/打码隐私，绝不改写。"""
    cleaned = clean_text(answer)
    if cleaned["dropped"] or not cleaned["text"]:
        return None
    user_content = (
        f"（{item['context']}）{item['question']}" if item["context"] else item["question"]
    )
    messages = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": cleaned["text"]},
    ]
    flags = ["风险"] if cleaned["flags"] else []
    return new_sample(
        source="questionnaire",
        scene=scene.id,
        messages=messages,
        flags=flags,
        status="approved",
        meta={"qid": qid(scene.id, item["idx"]), "context": item["context"]},
    )


def import_answers(
    store: SampleStore, doc: dict, scenes: dict[str, Scene], user_name: str = ""
) -> dict:
    """导入网页版 answers.json → 问卷样本（按 qid 去重，原文再走一次本地清洗）。"""
    added = skipped = 0
    existing: set[str] = set()
    for sid in scenes:
        existing |= answered_qids(store, sid)
    for ans in doc.get("answers") or []:
        qid_str = str(ans.get("qid") or "").strip()
        scene_id = str(ans.get("scene") or "").strip()
        if not scene_id and "#" in qid_str:
            scene_id = qid_str.split("#", 1)[0]
        scene = scenes.get(scene_id)
        answer = str(ans.get("answer") or "").strip()
        try:
            idx = int(qid_str.split("#", 1)[1])
        except (IndexError, ValueError):
            idx = -1
        if scene is None or not answer or not qid_str or idx < 0 or qid_str in existing:
            skipped += 1
            continue
        item = {
            "idx": idx,
            "context": str(ans.get("context") or ""),
            "question": str(ans.get("question") or ""),
        }
        sample = make_sample(scene, user_name, item, answer)
        if sample is None:
            skipped += 1
            continue
        store.add(sample)
        existing.add(qid_str)
        added += 1
    return {"added": added, "skipped": skipped}


def import_csv_rows(
    store: SampleStore, rows: list[dict], scenes: dict[str, Scene], user_name: str = ""
) -> dict:
    """导入已填 CSV（网页模板列 qid,scene_id,scene_name,context,question,answer）。

    - qid 优先；缺失时按（场景 + 题目原文）回退匹配题库
    - 题目原文/情境缺失时从题库自动回填（模板被删列也能导）
    - Excel 另存请选 “CSV UTF-8”
    """
    bank_by_qid: dict[str, dict] = {}
    bank_by_sq: dict[tuple[str, str], dict] = {}
    for sid, scene in scenes.items():
        for b in load_bank(scene):
            item = {"idx": b["idx"], "context": b["context"], "question": b["question"]}
            bank_by_qid[qid(sid, b["idx"])] = item
            bank_by_sq[(sid, b["question"])] = item
    scene_by_name = {s.name: s for s in scenes.values()}

    answers: list[dict] = []
    for row in rows:
        scene_id = (row.get("scene_id") or "").strip()
        if not scene_id:
            scene = scene_by_name.get((row.get("scene_name") or "").strip())
            scene_id = scene.id if scene else ""
        answer = (row.get("answer") or "").strip()
        if not scene_id or not answer:
            continue
        question = (row.get("question") or "").strip()
        context = (row.get("context") or "").strip()
        qid_str = (row.get("qid") or "").strip()

        hit = bank_by_qid.get(qid_str) if qid_str else bank_by_sq.get((scene_id, question))
        if hit is None and qid_str:
            continue  # qid 无效且无法匹配
        if hit is not None:
            qid_str = qid_str or qid(scene_id, hit["idx"])
            question = question or hit["question"]
            context = context or hit["context"]
        if not qid_str:
            continue
        answers.append(
            {"qid": qid_str, "scene": scene_id, "context": context,
             "question": question, "answer": answer}
        )
    return import_answers(store, {"answers": answers}, scenes, user_name)
