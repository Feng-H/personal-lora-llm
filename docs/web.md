# 网页版问卷（零安装入口）架构说明

## 定位：分层漏斗

```text
Level 1 零安装（本页主题）：
  网页问卷 → 浏览器直接导出 train.jsonl → Kaggle 训练 → GGUF → Ollama
  全程不装任何东西，手机也能填

Level 2 本地全功能：
  clone 仓库 → Streamlit 工作台 → 对话采集（需本地 LLM）+ IM 抽取（需本地 embedding）
  → 与网页导入的问卷样本合并 → 完整人格
```

为什么对话采集 / IM 抽取不能上网页：它们依赖本地 Ollama（采访 Agent）和本地
embedding 模型（bge-small-zh），纯静态页无法承载；而问卷通道只需要「读题库 → 收输入 →
拼 jsonl」，浏览器绰绰有余。

## 隐私模型（比本地版更严格）

- 纯静态站（GitHub Pages），无后端、无统计脚本、无 Cookie 追踪
- 填写内容只保存在浏览器 `localStorage`（key: `pplora.web.v1`），关闭页面不丢
- 导出文件由浏览器内存直接生成下载，**数据从头到尾不经过任何服务器**
- 题库内容（bank.js）本身是公开的项目资产，不含任何用户数据

## 文件与职责

| 文件 | 职责 |
| --- | --- |
| `web/index.html` | 页面骨架（三步：设置 → 填写 → 导出） |
| `web/style.css` | 暖纸 + 锈红视觉（与书站同族），移动端优先，自动深色 |
| `web/app.core.js` | 纯逻辑：隐私打码 / 样本构建 / 70·120 阈值校验 / train-val 切分 / CSV 解析（node 可测） |
| `web/app.js` | DOM 交互：localStorage 自动保存、导入导出（全程 createElement+textContent，不用 innerHTML） |
| `web/data/bank.js` | **生成产物**：由 `scripts/build_web_bank.py` 从 CSV+YAML 生成，勿手改 |
| `scripts/build_web_bank.py` | 题库构建：CSV+YAML → bank.js；`--check` 供 CI 防漂移 |
| `scripts/test_web_core.js` | 核心逻辑测试：`node scripts/test_web_core.js` |

## 与本地工作台的一致性

网页核心逻辑与 Python 侧逐条对齐：

- 隐私打码规则 ↔ `persona_lora/cleaning.py`（手机号/身份证/银行卡/邮箱/链接）
- messages 结构与结尾 assistant 约束 ↔ `persona_lora/export.py`
- 70 基础线 / 120 最优 / 多场景每场景 45 条强制校验 ↔ 同一套阈值
- qid 格式 `{scene_id}#{idx}` ↔ `persona_lora/questionnaire.py`

## 数据回流（网页 → 工作台）

网页导出的 `answers.json` 保存**未打码原文**（lossless），回传本地后走一次权威清洗管线：

- 工作台：`问卷采集` 页 → 导入 answers.json / 已填 CSV
- 命令行：`python -m persona_lora.cli import-answers --file answers.json`

反过来，`answers.json` 也能在网页端导入（换设备迁移），题库按 qid 匹配去重。

## 自定义题库并发布自己的问卷站

1. 改 `questionnaires/*.csv` 和 `config/scenes/*.yaml`（题库单一数据源）
2. `python scripts/build_web_bank.py` 重新生成 bank.js
3. Fork 本仓库 → Settings → Pages → Source 选 **GitHub Actions** → push 即自动部署
   （CI 会先 `--check` 校验 bank.js 与源头一致，防止忘重新生成）

## 本地预览网页

```bash
# 无需任何依赖，直接开文件也行；或：
python -m http.server -d web 8000   # http://localhost:8000
```
