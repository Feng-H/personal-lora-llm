# 硬件适配文档

## 训练阶段（推荐 Kaggle，零成本）

| 基座模型 | Kaggle T4（免费） | 时长参考 | 说明 |
| --- | --- | --- | --- |
| Qwen2.5-3B-Instruct | ✅ 轻松 | ~1 小时 | 极低门槛，人格上限较低 |
| **Qwen3.5-6B-Instruct（默认）** | ✅ 完全够用 | 2–3 小时 | 性价比最优，主推 |
| Qwen3.5-14B-Instruct | ⚠️ 谨慎 | 更久 | 建议有 P100/V100 级别再考虑 |

- 训练精度：4bit QLoRA（Unsloth），T4 16G 显存无压力
- 产物：几十 MB LoRA 适配器（不生成完整大模型）

## 推理阶段（本地部署矩阵）

| 设备 | 方案 | 内存需求 | 体验 |
| --- | --- | --- | --- |
| **Mac M1/M2/M3 8G** | Ollama GGUF Q4_K_M 或 MLX 4bit | 整机占用 ~3.5G，压力全绿 | 流畅 |
| Mac 16G+ | 同上 / Q6 更高精度 | 更宽裕 | 流畅 |
| Windows/Linux + 8G 内存 | Ollama / llama.cpp Q4 | ~4-5G | 流畅 |
| 有 NVIDIA 显卡 | Ollama / vLLM + PEFT | 依显存 | 极流畅 |

### Mac MLX 路线（最适合 Apple Silicon）

```bash
pip install mlx-lm
# Kaggle 下载 persona_merged 后：
./scripts/mlx_convert.sh persona_merged persona-mlx 4
python3 -m mlx_lm generate --model persona-mlx --prompt "这周末有空吗？"
```

### Ollama 路线（全平台通用）

```bash
# Kaggle 导出 GGUF（notebook 第 6 格 EXPORT_GGUF=True）后：
python scripts/make_ollama.py --gguf persona_gguf/unsloth.Q4_K_M.gguf --name my-persona
ollama create my-persona -f Modelfile.persona
python scripts/chat_test.py --model my-persona
```

### 已有 PEFT 适配器（不转 GGUF）

```bash
pip install peft transformers
python - <<'EOF'
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
base = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.5-6B-Instruct", torch_dtype="auto")
model = PeftModel.from_pretrained(base, "persona_lora_adapter")
model = model.merge_and_unload()
model.save_pretrained("persona_merged")
EOF
```

## 为什么推理阶段没有 RAG

本项目的定义：**RAG/向量检索只用于训练集素材预处理（IM 抽取）**。最终成品 = 基座 + LoRA 纯模型推理——模型真正学会了你的人格，而不是检索拼接话术。这样部署最轻、响应最快、离线可用、无知识库依赖。
