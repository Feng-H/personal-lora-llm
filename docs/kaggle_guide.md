# Kaggle 训练保姆级指南

## 0. 前置

- 本地已完成数据采集与审核，导出了 `train.jsonl`（≥70 条，建议 120+）
- 注册 [Kaggle](https://www.kaggle.com/) 账号（免费，每周 30h GPU）

## 1. 上传数据集（私有）

1. Kaggle 首页 → **Datasets** → **New Dataset**
2. 拖入 `train.jsonl` 和 `validation.jsonl`（若导出时生成了验证集）
3. 标题随意（如 `my-persona-data`），可见性务必 **Private**
4. Create

## 2. 同步 Notebook 到 Kaggle（三选一）

### 方式 A · GitHub 链接导入（零配置，最快）

Kaggle → **Code → New Notebook** → **File → Import Notebook** → 粘贴仓库里 notebook 的 GitHub 链接：

```text
https://github.com/Feng-H/personal-lora-llm/blob/main/notebooks/kaggle_persona_lora.ipynb
```

然后手动：右侧 **Add Input** 挂 `my-persona-data`；Settings 里开 **GPU** 与 **Internet**。
（一次性拷贝，仓库后续更新不会自动同步，需重新导入）

### 方式 B · kaggle CLI 同步（推荐，可重复）

一次性准备 token（仅此一步需手动）：

1. https://www.kaggle.com/settings → **API → Create New Token**（下载 kaggle.json）
2. `mkdir -p ~/.kaggle && mv ~/Downloads/kaggle.json ~/.kaggle/ && chmod 600 ~/.kaggle/kaggle.json`

之后每次同步只要一条命令：

```bash
./scripts/sync_kaggle.sh push    # 仓库 notebook → Kaggle
                                 # 自动配好：private + GPU + Internet + 预挂数据集
./scripts/sync_kaggle.sh pull    # Kaggle 上改过的版本拉回本地对比
./scripts/sync_kaggle.sh pull --apply   # 确认后回写仓库 notebook
./scripts/sync_kaggle.sh check   # 不动远端，只校验本地配置
```

- 数据集 slug 在 `notebooks/kernel-metadata.json` 的 `dataset_sources`（默认 `my-persona-data`，与你上传时命名一致即可自动预挂；不存在则自动降级为不挂载并提示）
- 也可配 GitHub Actions 全自动同步：`.github/workflows/kaggle-sync.yml`（需在仓库 Secrets 配 `KAGGLE_USERNAME`/`KAGGLE_KEY`，手动触发）

### 方式 C · 手动上传

**File → Import Notebook** → 上传本地 `notebooks/kaggle_persona_lora.ipynb`，再同方式 A 手动配数据集与算力。

### 无论哪种方式，确认 Settings

- **Accelerator**: GPU **T4 x2**（用一张即可；CLI push 默认 GPU，卡型可在此切换）
- **Internet**: **On**（安装 unsloth 需要）

## 3. 运行

- 直接 **Run All**
- 配置区默认：`Qwen3.5-6B-Instruct` + LoRA r16 + epoch 3 + lr 2e-4 + 早停
- 想换基座只改 `BASE_MODEL` 一行

## 4. 常见问题

| 现象 | 处理 |
| --- | --- |
| `AssertionError: 未找到 train.jsonl` | 右侧没挂载数据集 → Add Input |
| pip 安装失败/超时 | Settings → Internet 没开 |
| OOM 显存 | `BATCH_SIZE` 改 1；或基座换 3B |
| loss 早早不降/过拟合 | 已内置早停；也可把 `EPOCHS` 降为 2 |
| 训练完想直接 Ollama | 第 6 格 `EXPORT_GGUF = True` 重跑该格 |

## 5. 下载产物并本地部署

1. 下载 `persona_lora_adapter.zip`（或 GGUF zip / merged zip）
2. 见 `docs/hardware.md`：Ollama / MLX / llama.cpp 三条路线
3. `python scripts/chat_test.py` 开始和你的分身聊天
