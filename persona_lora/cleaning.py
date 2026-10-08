"""数据清洗（铁律实现）。

人格特征全部保留：语气词、口头禅、感叹号、换行、刻意重复强调、标点习惯。
仅剔除纯噪声：乱码、链接、表情包占位、系统消息、无意义单字碎片；
隐私明文不删除、只打码 + 标记【风险】，最终决策权永远归用户。
"""
from __future__ import annotations

import re

# ---- 隐私明文（打码 + 标记，不删除）----
PRIVACY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("手机号", re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")),
    ("身份证", re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")),
    ("邮箱", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("链接", re.compile(r"https?://\S+|www\.\S+")),
    ("银行卡", re.compile(r"(?<!\d)\d{16,19}(?!\d)")),
]

# ---- 纯噪声（整条消息级别剔除）----
EMOJI_PLACEHOLDER = re.compile(
    r"^[\s\[【（(]*(图片|表情|动画表情|语音|视频|文件|名片|红包|转账|位置|链接|"
    r"emoji|sticker|image|voice|video|file)[\]】）):\s]*$"
)
SYSTEM_NOTICE = re.compile(
    r"(撤回了一条消息|拍了拍|红包封面|已领取|加入了群聊|移出了群聊|"
    r"朋友验证|暂不支持的消息类型|以上消息|下列消息|对方正在输入|消息已发出，但被对方拒收)"
)
MOJIBAKE = re.compile(r"(ï¿½|Ã¢|â€|ï»¿|å¼|é”™|çš„)")
# 无意义单字碎片：单个 ASCII 字母/数字/标点（中文单字如"嗯/哦/好"是人格，保留）
FRAGMENT = re.compile(r"^[a-zA-Z0-9\W_]$")

TRAILING_NOISE = re.compile(r"[\s\u200b\ufeff]+")


def is_noise_message(text: str) -> str | None:
    """整条消息是否为纯噪声；返回噪声类型，非噪声返回 None。"""
    t = text.strip()
    if not t:
        return "空消息"
    if EMOJI_PLACEHOLDER.match(t):
        return "表情包占位"
    if SYSTEM_NOTICE.search(t):
        return "系统消息"
    if MOJIBAKE.search(t) and len(re.sub(r"[\w\u4e00-\u9fff，。！？\s]", "", t)) > len(t) * 0.3:
        return "乱码"
    if FRAGMENT.match(t):
        return "无意义单字碎片"
    return None


def mask_privacy(text: str) -> tuple[str, list[str]]:
    """隐私明文打码（保留占位标记），返回 (处理后文本, 命中类型列表)。"""
    hits: list[str] = []
    out = text
    for label, pat in PRIVACY_PATTERNS:
        if pat.search(out):
            hits.append(label)
            out = pat.sub(f"【{label}】", out)
    return out, hits


def clean_text(text: str) -> dict:
    """单条用户原文清洗：只动噪声与隐私，绝不改写语气/标点/重复。

    返回 {text, dropped(噪声类型|None), flags(如["风险:手机号"])}
    """
    t = TRAILING_NOISE.sub(" ", text).strip()
    dropped = is_noise_message(t)
    if dropped:
        return {"text": "", "dropped": dropped, "flags": []}
    masked, hits = mask_privacy(t)
    flags = [f"风险:{h}" for h in hits]
    return {"text": masked, "dropped": None, "flags": flags}


def scan_flags(messages: list[dict]) -> list[str]:
    """对样本做规则质检：只标记、不删除、不去重（刻意重复是人格特征）。"""
    flags: list[str] = []
    assistant_texts = [m["content"] for m in messages if m.get("role") == "assistant"]
    joined = "\n".join(assistant_texts)
    _, hits = mask_privacy_unmutated(joined)
    if hits:
        flags.append("风险")
    # 低质量：assistant 全部为超短敷衍句
    if assistant_texts and all(len(a) <= 3 for a in assistant_texts):
        flags.append("低质量")
    # 人工复核：同一句原文出现 ≥3 次（可能是刷屏，也可能刻意强调——交给人判）
    if assistant_texts:
        seen: dict[str, int] = {}
        for a in assistant_texts:
            seen[a] = seen.get(a, 0) + 1
        if max(seen.values()) >= 3:
            flags.append("人工复核")
    return flags


def mask_privacy_unmutated(text: str) -> tuple[str, list[str]]:
    """只检测不修改：返回 (原文, 命中类型列表)。"""
    hits = [label for label, pat in PRIVACY_PATTERNS if pat.search(text)]
    return text, hits
