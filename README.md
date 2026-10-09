# Personal Persona LoRA · 个人真实人格 AI-LoRA 全自动复刻系统

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB)](https://python.org)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B)](https://streamlit.io)
[![Train on Kaggle T4](https://img.shields.io/badge/Train-Kaggle_T4_Free-20BEFF)](https://kaggle.com)
[![在线问卷](https://img.shields.io/badge/在线问卷-GitHub_Pages-blue)](https://feng-h.github.io/personal-lora-llm/)

> **完全私有化 · 用户自助 · 零服务端** 的「真实人类语言人格复刻 LoRA」全自动工作流。
> 不复刻标准答案，只复刻真实人格：语气词、口头禅、标点风格、换行习惯、刻意重复强调、个人口语瑕疵——全部保留。

📖 姊妹项目：[《通过 Google Colab / Kaggle 学习模型微调》开源专著](https://feng-h.github.io/finetune-colab-kaggle-mac/)（本项目训练/部署方法论的理论基础）

---

## ✨ 核心独创（区别全网同类项目）

| # | 理念 | 说明 |
| --- | --- | --- |
| 1 | **行业首个主动式人格采集 Agent** | 市面 Agent 全是被动应答；本项目独家实现「被动闲聊 + 智能主动补齐」双模式：场景缺口检测 / 结构缺陷检测 / 空闲定时三级触发，严格限流防骚扰 |
| 2 | **三套数据采集体系融合** | 问卷冷启动 + AI 自然对话积累 + 历史聊天批量抽取，解决手动填表失真、纯聊天数据杂乱、存量数据浪费三大痛点 |
| 3 | **彻底尊重人类个性** | 不删语气词、不删重复强调、不标准化口语、机器只标记不删除、最终决策权归用户 |
| 4 | **RAG 只做预处理，推理干净纯粹** | 向量检索仅用于 IM 训练素材抽取；最终成品 = 基座 + 个人 LoRA 纯模型推理，无检索、无外挂、无知识库 |
| 5 | **全链路隐私安全** | 作者零数据、零中转、零上传；所有数据/权重 100% 归属用户 |
| 6 | **全民可用** | 免费 Kaggle T4 训练 + Mac M1 8G 流畅推理，无显卡也能玩 |

## 🗺️ 全链路架构

```text
场景选择 → 三通道采集 → 统一清洗质检 → 人工审核 → train.jsonl
              ↑                                    ↓
   问卷 / 双向Agent / IM向量抽取        Kaggle Unsloth 一键 LoRA 训练
                                                   ↓
                              LoRA 适配器 → GGUF / MLX → 本地纯模型推理
```

## 🚀 极速上手：两种入口，按需选择

### 入口 A · 网页版问卷（零安装，手机也能填）🆕

打开**在线问卷** 👉 **https://feng-h.github.io/personal-lora-llm/** ，浏览器里直接填（fork 用户开自己的 Pages 后是 `https://<你的用户名>.github.io/personal-lora-llm/`，见 docs/web.md）：

```text
网页填问卷（30 分钟）→ 浏览器直接下载 train.jsonl → 上传你的 Kaggle 训练
→ 下载 GGUF → ollama run 我的分身
```

- 数据只存在浏览器 localStorage，零上传零服务器（见 docs/web.md 隐私模型）
- 不想逐题填？网页可下载**空白 CSV 模板**用 Excel 离线填再回传，或下载
  `answers.json` 后回传本地工作台，与对话/IM 样本合并
- 入口 B 需要的功能（对话采集、IM 抽取）依赖本地 LLM/向量模型，网页无法承载

### 入口 B · 本地工作台（全功能）

#### 1. 安装（本地，Python 3.10+）

```bash
git clone https://github.com/Feng-H/personal-lora-llm.git
cd personal-lora-llm
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

可选（强烈推荐，用于对话采集与 IM 质检）：

```bash
ollama serve &
ollama pull qwen3:8b
```

#### 2. 打开工作台

```bash
streamlit run app/Home.py
```

#### 3. 三通道攒数据

| 通道 | 入口 | 产出 |
| --- | --- | --- |
| 📝 问卷冷启动 | 工作台 → 问卷采集 | 30 分钟打底 30-80 条干净样本 |
| 💬 双向对话采集（王牌） | 工作台 → 对话采集 | 日常聊天自然积累，AI 主动补齐薄弱场景 |
| 📥 IM 历史抽取 | 工作台 → IM 导入 | 微信/QQ 导出 txt → 向量场景检索 → LLM 标记 → 人工确认 |

样本目标：**≥70 条可训练（基础版人格），≥120 条最优（完整版人格）**。

#### 4. Kaggle 一键训练

工作台「导出训练」页下载 `train.jsonl` → 同步 Notebook 到你的 Kaggle（四选一，见 [docs/kaggle_guide.md](docs/kaggle_guide.md)）：
GitHub 链接导入 / **Fork 后配 1 个 Secret 全自动同步（零克隆，方式 B+）** / `./scripts/sync_kaggle.sh push` / 手动上传。免费 T4，默认 Qwen3.5-6B + 4bit + LoRA r16 + epoch 3 + 早停，约 2-3 小时，产出几十 MB 适配器。

#### 5. 本地部署你的分身

```bash
# Ollama（全平台）
python scripts/make_ollama.py --gguf <gguf文件> --name my-persona
ollama create my-persona -f Modelfile.persona
python scripts/chat_test.py

# Mac MLX（Apple Silicon 最优）
./scripts/mlx_convert.sh persona_merged persona-mlx 4
```

## 📁 仓库结构

```text
config/scenes/        7 大场景配置（可自定义扩展）
questionnaires/       场景化问卷题库（真实问答对）
persona_lora/         核心库：采集/清洗/质检/统计/导出/CLI/Agent桥接
app/                  Streamlit 工作台（5 大页面）
notebooks/            Kaggle Unsloth 一键训练 Notebook
scripts/              Ollama / MLX / 对话测试脚本
docs/                 场景说明 · Kaggle 指南 · 硬件适配 · FAQ · 隐私 · 宿主接入
```

## 🧹 清洗铁律（与所有「数据工程」教程相反）

- **保留**：语气词、口头禅、感叹号、换行、刻意重复三遍的强调句、个人句式瑕疵
- **仅剔除**：乱码、链接、表情包占位、系统消息、无意义单字碎片
- **隐私明文**：打码 + 【风险】标记，不删除
- **重复不强制去重**：刻意强调属于人格特征
- **机器只做标记**：【人工复核】【风险】【低质量】，定稿权在你

## 🔒 隐私与合规

本项目仅为模板工作流，**作者不接触任何用户数据**；不提供任何 IM 逆向破解代码；embedding/抽取/推理全部本地私有化。详见 [docs/privacy.md](docs/privacy.md)。开源协议 MIT。

## 🗺️ Roadmap

- [x] 三通道采集 + 审核导出 + Kaggle 训练 + 多格式部署（v0.1）
- [ ] 英文场景包与英文人格复刻
- [ ] 自动化人格评测（分身 vs 本人的风格盲测）
- [ ] 更多基座模型适配（GLM / Gemma / Llama）

---

## English Summary

A fully local, serverless, privacy-first pipeline that replicates **your real speaking style** into a personal LoRA adapter: three-channel data collection (scenario questionnaires / proactive chat agent / IM history vector extraction), fidelity-first cleaning (never polish, never dedupe your personality), human-in-the-loop review, one-click Unsloth training on free Kaggle T4, and pure model inference (no RAG at runtime) on Ollama / MLX / llama.cpp. MIT licensed.
