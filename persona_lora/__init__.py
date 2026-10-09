"""Personal Persona LoRA —— 个人真实风格 AI-LoRA 复刻系统核心库。

三通道数据采集（问卷冷启动 / 双向对话 Agent / IM 历史抽取）
→ 统一清洗质检 → messages jsonl 训练集 → Kaggle Unsloth LoRA 训练 → 本地多格式部署。
"""

__version__ = "0.1.0"

from .config import ROOT, Config, load_config  # noqa: F401
from .scenes import Scene, load_scenes, selected_scenes  # noqa: F401
