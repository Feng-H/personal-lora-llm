# 场景体系说明

## 场景池（config/scenes/*.yaml）

| 场景 id | 名称 | 定位 |
| --- | --- | --- |
| `work_communication` | 💼 通用职场沟通 | 同事协作、进度同步、汇报、跨部门协调 |
| `product_manager` | 📋 产品经理专属 | 需求评审、优先级博弈、数据决策 |
| `engineer` | 💻 研发工程师专属 | Code Review、线上事故、技术选型 |
| `project_management` | 📅 项目管理专属 | 里程碑、风险、资源、复盘 |
| `daily_social` | 🍜 日常生活社交 | 朋友闲聊、安慰陪伴、拒绝请求 |
| `family_parenting` | 👨‍👩‍👧 家庭亲子辅导 | 作业辅导、情绪引导、家校沟通 |
| `study_writing` | ✍️ 学习 / 书面写作 | 笔记、总结、邮件、观点表达 |

每个场景包含：

- `system_prompt`：训练样本的系统提示词（`{user_name}` 自动替换）
- `min_samples_single` / `min_samples_multi`：单场景 / 多场景模式的最低样本阈值
- `questionnaire`：问卷题库 CSV（真实场景问答对）
- `retrieval_queries`：IM 历史向量检索关键词
- `interview_angles`：AI 采访者的提问角度
- `openers` / `proactive_topics`：主动发起的开场与深度话题池

## 两种用户模式

- **单场景专精（新手推荐）**：只训练单一人格，风格纯净、不串味、快速成型。目标 70+ 条。
- **多场景全能（进阶）**：多场景合并采集训练，模型可自动区分「工作严谨、生活松弛、育儿耐心」等风格切换。
  系统内置强制校验：**每个勾选场景都必须达到 `min_samples_multi`（默认 45 条）**，否则导出被拦截，防止风格混杂。

## 自定义场景

1. 复制任意一个 `config/scenes/*.yaml` 为新场景（改 `id` / `name` / 提示词 / 关键词 / 话题池）
2. 在 `questionnaires/` 下建同名 CSV（列：`context,question`，全部为「别人会怎么问」的真实情境）
3. 重启 Streamlit，新场景自动出现在首页勾选列表中

## 主动发起机制（防骚扰铁律）

- 触发优先级：**场景样本缺口 > 结构缺陷（敷衍短句过多）> 空闲定时（默认 7 分钟）**
- 单轮会话最多主动 1 次；单日最多 3 次（可配置）
- 连续 2 次无视/拒绝 → 自动降级永久被动模式
- 有效样本 ≥ 120 条 → 自动关闭所有主动采集
