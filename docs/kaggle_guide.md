# Kaggle 训练保姆级指南

## 0. 前置

- 本地已完成数据采集与审核，导出了 `train.jsonl`（≥70 条，建议 120+）
- 注册 [Kaggle](https://www.kaggle.com/) 账号（免费，每周 30h GPU）

## 1. 上传数据集（私有）

1. Kaggle 首页 → **Datasets** → **New Dataset**
2. 拖入 `train.jsonl` 和 `validation.jsonl`（若导出时生成了验证集）
3. 标题随意（如 `my-persona-data`），可见性务必 **Private**
4. Create

## 2. 导入 Notebook

1. **Code** → **New Notebook** → File → **Import Notebook** → 上传 `notebooks/kaggle_persona_lora.ipynb`
2. 右侧面板 **Add Input** → Your Datasets → 选中 `my-persona-data`
3. Settings：
   - **Accelerator**: GPU **T4 x2**（用一张即可）
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
