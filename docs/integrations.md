# Hermes / OpenClaw 等外部 Agent 宿主接入

本项目的对话采集 Agent 可作为**子命令**挂进你常驻的 AI 助手（OpenClaw、Hermes 等），让日常聊天自然沉淀训练样本，无需打开 Streamlit。

## 桥接协议（persona_lora.bridge）

宿主只需 shell 调用，输入输出全部 JSON：

```bash
# 用户发消息 → AI 承接回复（自动打包样本）
python -m persona_lora.bridge --session openclaw --message "最近好忙啊"
# → {"reply": "忙啥呢这么拼？展开说说", "proactive": null, "total_samples": 42}

# 空闲轮询 → 独立主动搭话（建议宿主每 1-2 分钟调度一次）
python -m persona_lora.bridge --session openclaw --poll-proactive
# → {"proactive": "哎对了，最近工作里有没有什么让你特别无语的事？"}

# 用户无视了主动话题 → 记一次无视（连续 2 次自动降级永久被动）
python -m persona_lora.bridge --session openclaw --note-ignore

# 结束会话并封存样本
python -m persona_lora.bridge --session openclaw --close
```

## OpenClaw 接入示例（skill 片段）

把桥接命令包装成宿主可调用的工具/技能，聊天路由规则：

```text
用户消息 → persona_lora.bridge --message <msg>
回复内容 = $.reply
后台每 90s → persona_lora.bridge --poll-proactive，若 $.proactive 非空则主动发送
```

## 前置条件

- 本地 LLM 服务（Ollama：`ollama serve` + `ollama pull qwen3:8b`），配置见 `config/system.yaml` 的 `llm` 段
- 在本仓库目录运行（`python -m persona_lora.bridge` 需要项目在 `sys.path`）

## 设计边界

- 采集侧的 AI（采访者）是你本地的小模型，只负责陪聊与引导；**你的风格最终由 LoRA 学习，不依赖这个采访模型**
- 所有会话与样本仍落在本仓库 `data/` 下，宿主只是「传声筒」，不存储数据
