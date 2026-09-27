# LabPilot

<div align="center">

### 让每个人都能拥有一位 AI 科研搭档。

**从一个想法，到一组值得相信的实验。**

[简体中文](README.md) · [English](README.en.md) · [快速体验](#快速体验) · [未来路线](#未来路线) · [实测记录](docs/phase10-report.md)

[![GitHub Stars](https://img.shields.io/github/stars/JackZhu001/LabPilot?style=social)](https://github.com/JackZhu001/LabPilot)
[![最近更新](https://img.shields.io/github/last-commit/JackZhu001/LabPilot)](https://github.com/JackZhu001/LabPilot/commits/main)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB)

</div>

## 想做实验，从一句话开始

> “我想改善这个模型的泛化能力。这是参考论文和 baseline，请帮我调研、提出方案，并在训练预算内验证。”

**这是我们想实现的科研体验：你定义问题和边界，AI 帮你把想法一步步推进成可核验的证据。** 从读论文、提出假设，到改配置、跑实验、比较结果，让每一步的来龙去脉都能被看见，让每一次失败都能为下一次尝试留下依据。

LabPilot 正在向这个目标构建。目前已打通有边界的机器学习研究流程：自定义研究任务、文献证据、DeepSeek 规划、Docker 实验、多种子评估与可恢复报告。通用任务适配和跨研究知识积累是后续方向。

**如果你也期待这样的 AI 科研搭档，欢迎点一个 Star，收藏项目并关注后续进展。** 有希望优先支持的任务，可以直接[提一个 Issue](https://github.com/JackZhu001/LabPilot/issues/new)。

<p align="center">
  <img src="docs/images/dashboard-zh.png" alt="LabPilot 中文工作台：研究运行、实验指标与活动记录" width="960" />
</p>

*中文研究工作台 · 截图展示本地演示运行；首页 3D 场景为装饰效果。*

## 今天，你可以怎么用它

| 你的起点 | LabPilot 已支持的流程 |
| --- | --- |
| **一个研究主题** | 设置目标、文献预算和约束，检索论文并形成研究假设。 |
| **几篇参考论文** | 上传最多 5 篇论文，提取带原文片段的论点，追踪证据与假设的关联。 |
| **自己的 baseline** | 指定符合运行契约的干净本地 Git 仓库，设置指标、随机种子和允许改动范围。 |
| **一个想验证的配置** | 在隔离 Docker 环境运行实验，支持 Optuna 调参、已保存配置方案的多种子验证。 |
| **一段中断的研究** | 从 SQLite 检查点续跑，用已有状态生成 Markdown / JSON 报告。 |

创建研究时，你可以先检查任务和预算预览，再启动运行。DeepSeek 负责研究规划与可选代码方案；Jev 可通过 OpenRouter 辅助判断文献证据。实验的保留、拒绝或重新规划依据测量指标和明确阈值。

## 从任务到结果，看得见每一步

```text
研究主题 / 论文 / baseline
          ↓
    文献检索与原文证据
          ↓
      研究假设与实验计划
          ↓
    隔离实验与指标比较
          ↓
  保留 / 拒绝 / 重新规划
          ↓
    可追溯、可恢复的报告
```

按流程展开查看界面。每张截图单独展示，点击图片可查看原图。

<details>
<summary><strong>01 · 定义研究：主题、论文、baseline 和约束</strong></summary>

把研究目标与实验边界放在同一份任务里，支持目标指标、随机种子、文献数量和改动范围设置。

<img src="docs/images/new-research-advanced-zh.png" alt="自定义研究设置" width="800" />

</details>

<details>
<summary><strong>02 · 启动前预览：检查 baseline 与研究预算</strong></summary>

确认仓库、目标指标和实验上限后启动研究。文献综述与具体假设在运行中生成。

<img src="docs/images/research-plan-preview-zh.png" alt="中文研究计划预览" width="800" />

</details>

<details>
<summary><strong>03 · 查看结果：指标、决策与研究记录</strong></summary>

从保存的研究状态查看实验结果，导出报告，回查代码和运行条件。

<img src="docs/images/report-detail-zh.png" alt="研究报告与实验结果" width="800" />

</details>

<details>
<summary><strong>04 · English interface：工作台、计划与报告</strong></summary>

**Research dashboard**

<img src="docs/images/dashboard-en.png" alt="English research dashboard" width="800" />

**Plan preview**

<img src="docs/images/research-plan-preview-en.png" alt="English research plan preview" width="800" />

**Report**

<img src="docs/images/report-en.png" alt="English report preview" width="800" />

</details>

## 快速体验

**先体验完整工作台，无需 API key，也无需 Docker。** 以下流程生成一条模拟研究记录，用于熟悉界面；不会执行真实训练。

准备 Python 3.11+、[uv](https://docs.astral.sh/uv/getting-started/installation/) 和 Node.js。

```bash
git clone https://github.com/JackZhu001/LabPilot.git
cd LabPilot
uv sync --locked --extra dev
uv run labpilot run --goal "Does dropout improve validation accuracy?"
uv run labpilot serve-api --db .labpilot/labpilot.sqlite3
```

另开终端，在仓库目录启动前端：

```bash
cd frontend
npm ci
npm run dev
```

打开终端显示的本地地址。工作台支持中英文、深浅主题与动画开关。

**准备运行真实研究？** 安装 Docker，配置服务端 `DEEPSEEK_API_KEY`，参考[真实实验说明](README.en.md#phase-2-isolated-real-execution)和[DeepSeek 研究配置](README.en.md#phase-4-structured-agent-harness)。选择 Jev 时还需 `OPENROUTER_API_KEY`；根目录 `.env` 不会自动加载。完整命令见 [CLI 手册](README.en.md#cli-examples)。

## 已经跑过，而不只是计划

目前内置 **MNIST、FashionMNIST、CIFAR-10** 三个图像基准，并记录了真实 Docker 实验与多种子结果。

- **FashionMNIST：** 已保存的 DeepSeek 配置方案完成 8 种子评估；配对变化均值约 +0.00069，样本标准差约 0.00954，未显示稳定收益。[查看记录](docs/phase9-report.md)
- **CIFAR-10：** 完成 3 种子试跑和扩展 8 种子评估。扩展批次平均准确率变化 −0.0123，8 个种子均拒绝该 dropout 设置。[查看记录](docs/phase10-report.md)

负结果也是研究产物：保留实验条件和拒绝理由，才能判断一个想法是否值得继续。以上结论仅适用于报告中的小规模训练配置，不代表通用科研能力或 SOTA 性能。

## 未来路线

**长期愿景：让一次实验的终点，成为下一次研究的起点。** 逐步构建能积累实验经验、适配更多任务、由研究者控制方向的 AI 实验室。

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 研究闭环 | 文献、假设、隔离实验、指标决策、检查点与报告 | 已实现有边界版本 |
| 自定义研究 | 上传论文、指定 baseline、目标指标与研究约束 | 已实现 |
| 可复核评估 | 三个图像基准、多种子运行、方案来源追踪 | 已有实测记录 |
| 更广的任务适配 | 更多数据集、训练入口和可复用实验模板 | 规划中 |
| 更可靠的长任务 | 任务队列、并行执行与异常恢复 | 规划中 |
| 可复用研究接口 | 完善 SDK 与 runtime 接入体验 | 规划中 |
| 持续积累的研究记忆 | 将历史正负结果用于后续方案选择，并验证其收益 | 长期探索 |

规划项尚未交付，优先级会根据实际使用反馈调整。欢迎在 [Issues](https://github.com/JackZhu001/LabPilot/issues) 里描述你的研究任务、复现问题或希望支持的 baseline。

## 一起把它做成真正有用的科研工具

你可以带来一个真实研究场景、一份可复现 baseline，或一次失败记录。也欢迎参与任务模板、证据质量、运行恢复与界面体验的改进。

**觉得这个方向值得做，欢迎 Star；愿意试用，欢迎把结果和问题带回来。**

[English & 技术手册](README.en.md) · [前端文档](frontend/README.md) · [架构](README.en.md#architecture) · [阶段报告](docs/) · [提交反馈](https://github.com/JackZhu001/LabPilot/issues/new)

<details>
<summary>当前边界与运行说明</summary>

LabPilot 是有边界的研究自动化系统，目前没有实现通用自主科研或递归自我改进（RSI）。文献检索以 arXiv / Semantic Scholar 的元数据与摘要为主，也支持上传论文摘录。Jev 评估不能替代原文核验。自定义仓库需符合训练入口和指标输出契约；现有实验执行为本地、顺序运行。

研究流程中的 Jev 使用 OpenRouter Decisions API，固定模型为 `typesafe/jev-1.13`。独立 `labpilot judge-evidence` 命令走 TypeSafe 官方 API，需要 `TYPESAFE_API_KEY`。

</details>
