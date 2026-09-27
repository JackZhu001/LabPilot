# LabPilot

<div align="center">

### 从一个研究问题出发，走到可复核、可复现的实验结论。

LabPilot 把文献证据、机器学习假设、隔离实验与量化决策连成一条可恢复的研究流程。

[English](README.md) · [快速开始](#快速开始) · [查看实测报告](docs/phase10-report.md)

[![GitHub stars](https://img.shields.io/github/stars/JackZhu001/LabPilot?style=social)](https://github.com/JackZhu001/LabPilot/stargazers)
![最近更新](https://img.shields.io/github/last-commit/JackZhu001/LabPilot)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)
![React 19](https://img.shields.io/badge/UI-React%2019-61DAFB)

<img src="docs/images/dashboard-zh.png" alt="LabPilot 中文研究工作台" width="100%" />

</div>

研究不只是生成一个点子。还需要知道论据来自哪篇论文、实验改了什么、基线和随机种子是什么，以及结果为何被保留或拒绝。LabPilot 将这些信息连在同一份研究记录中，让成功结果更容易核验，让失败实验也能留下可复用的结论。

## 一条可审查的研究流程

| 定义问题 | 连接证据 | 控制实验 | 留下结论 |
| --- | --- | --- | --- |
| 设置主题、代码基线、目标指标、随机种子和约束。 | 检索 arXiv / Semantic Scholar，或上传论文；论点保留原文来源。 | 先预览计划，再用隔离 Docker 环境运行有预算边界的实验。 | 查看指标、代码差异、来源记录与 KEEP / REJECT / REPLAN 决策，并可从检查点续跑。 |

DeepSeek 用于研究规划和可选的代码方案；Jev 可通过 OpenRouter 提供结构化文献证据评估。实验决策以可测量结果和确定性规则为准。

## 看看工作台

中英文界面支持自定义研究任务、计划预览、证据追踪和已保存报告。截图使用本地演示数据；首页 3D 场景是装饰效果，图表与实验结论来自保存的运行记录。

<p align="center">
  <img src="docs/images/new-research-advanced-zh.png" alt="主题、基线、指标与高级研究设置" width="49%" />
  <img src="docs/images/research-plan-preview-zh.png" alt="研究计划预览" width="49%" />
</p>
<p align="center">
  <img src="docs/images/research-plan-preview-en.png" alt="English research plan preview" width="49%" />
  <img src="docs/images/report-detail-zh.png" alt="实验结果和研究报告" width="49%" />
</p>
<p align="center">
  <img src="docs/images/report-en.png" alt="English report preview" width="49%" />
  <img src="docs/images/dashboard-en.png" alt="English dashboard" width="49%" />
</p>

## 快速开始

无需模型密钥即可用模拟数据启动工作台。需要 Python 3.11+ 和 Node.js；只有真实隔离实验需要 Docker。

```bash
uv sync --locked --extra dev
uv run labpilot run --goal "Does dropout improve validation accuracy?"
uv run labpilot serve-api --db .labpilot/labpilot.sqlite3
```

另开一个终端启动前端：

```bash
cd frontend
npm ci
npm run dev
```

打开 Vite 显示的本地地址，即可在工作台查看刚生成的模拟运行。查看[前端运行说明](frontend/README.md)。真实 DeepSeek 研究需要 DeepSeek API key；Jev 证据评估需要服务端设置 `OPENROUTER_API_KEY`。密钥只应放在后端环境中，不要写入前端或提交到 Git。

## 自定义你的研究任务

在 **New research** 页面输入主题，可上传最多 5 篇论文，指定本地 Git baseline、目标指标、随机种子、文献预算和改动约束。启动前先检查仓库并预览计划；确认后再开始研究。实验在 Docker 中隔离运行，报告保留来源、代码差异、运行条件与测量结果。

## 一项真实的有限范围评估

Phase 10 增加 CIFAR-10 RGB 基线和宿主机校验的数据准备流程，使 Docker 训练容器保持离线。在扩展的 8 种子评估中，dropout 0.3 的验证准确率配对变化均值为 **−0.0123**（样本标准差 **0.0126**），8 个种子均未达到 KEEP 条件。这只说明该短训练配置没有显示稳定收益，不代表 dropout 普遍无效。[完整报告](docs/phase10-report.md)列出镜像、提交、种子、指标与局限。

## 面向可追溯性的工程设计

```text
研究任务 → 文献 → 原文论点 → 假设 → 可审查计划
                                  ↓
                           隔离实验 → 指标 → 决策 → 报告
```

核心记录由类型化研究状态、显式预算、Git 工作树、Docker、SQLite 检查点、Optuna HPO 和 Markdown / JSON 报告支撑。可查看[架构说明](README.md#architecture)、[CLI 示例](README.md#cli-examples)和[阶段报告](docs/)。

<details>
<summary>通过 OpenRouter 使用 Jev</summary>

在后端环境设置 `OPENROUTER_API_KEY`，并在新建研究页面选择 **Jev**。LabPilot 通过 OpenRouter Decisions API 调用固定模型 `typesafe/jev-1.13`，将关系、相关度、证据强度、token 用量和费用保存到证据记录。详见 [OpenRouter Jev 指南](https://openrouter.ai/blog/tutorials/how-to-use-jev/)。

独立 CLI 命令 `labpilot judge-evidence` 使用 TypeSafe 官方 API，需要单独设置 `TYPESAFE_API_KEY`。

</details>

<details>
<summary>当前范围与局限</summary>

内置视觉任务是小规模、有边界的基准；CIFAR-10 实验不是 SOTA 对比。文献检索使用 arXiv 和 Semantic Scholar 的元数据与摘要，也支持用户上传论文。Jev 判断仅作辅助，不能替代原文核查。LabPilot 是有边界的研究自动化工具，目前不应宣称已经实现递归自我改进（RSI）。

</details>

## 项目进度

Phase 1–10 已实现 MNIST、FashionMNIST 和 CIFAR-10 三个图像基准。CIFAR-10 已完成 11 个固定种子的 Docker 评估；扩展 8 种子批次未显示 dropout 0.3 的稳定收益。另有 DeepSeek 方案交接、多种子续跑、报告和来源追踪能力。详见 [Phase 7](docs/phase7-report.md)、[Phase 8](docs/phase8-report.md)、[Phase 9](docs/phase9-report.md) 与 [Phase 10](docs/phase10-report.md)。

## 开发验证

```bash
pytest -q
ruff check src tests
mypy src
cd frontend
npm run lint
npm run build
npm run smoke
```

前端烟雾检查涵盖路由渲染和语言翻译；默认后端测试不包含 Docker 或真实外部服务调用。
