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
