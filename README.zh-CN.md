# LabPilot

**自主机器学习研究与实验助手** · [English](README.md)

从文献证据到可测量的实验结果：LabPilot 将假设、代码变更、隔离执行、指标与决策连接到同一份可恢复的研究状态。

![LabPilot 中文研究工作台](docs/images/dashboard-zh.png)

## 可以做什么

- **文献与证据**：检索 arXiv / Semantic Scholar，提取可核对的摘要论点，保留论文、证据与假设之间的关联。
- **研究与实验**：DeepSeek 生成结构化研究计划、假设和补丁；通过 Git 工作树和 Docker 执行实验。
- **超参数优化**：Optuna 搜索空间、试验状态和预算持久化，支持失败后继续后续试验。
- **确定性决策**：依据真实指标与阈值选择保留、拒绝或重新规划，支持最大化与最小化目标。
- **报告与对比**：导出带版本和 SHA-256 指纹的 Markdown / JSON 报告，按记录的实验条件对比历史运行。
- **双语工作台**：中英文切换、深浅主题、交互式 3D 模型、页面与卡片动效、全局动画暂停以及系统减少动态效果支持。

研究目标、论文原文、代码、原始状态与导出快照保留原始语言。动画模型是视觉展示，不代表实时科研进度。

## 本地启动

需要 Python 3.11+，以及符合当前 Vite 版本要求的 Node.js。Docker 仅在运行真实隔离实验时需要。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
labpilot run --goal "Does dropout improve validation accuracy?"
labpilot serve-api
```

上面的研究命令使用默认离线模拟模式，不会产生真实训练结果。另开一个终端启动前端：

```bash
cd frontend
npm ci
npm run dev
```

打开终端显示的本地地址。顶栏可切换语言、动画与主题，偏好保存在本设备上。真实实验与 DeepSeek 配置请查看 [完整使用说明](README.md#setup)，密钥通过环境变量提供，不要提交到仓库。

## 报告

![研究报告预览](docs/images/report-en.png)

```bash
labpilot report RUN_ID --db .labpilot/labpilot.sqlite3 --format markdown > report.md
labpilot benchmark --db .labpilot/labpilot.sqlite3 --format json > benchmark.json
```

报告从已保存状态生成，不会调用大模型或重新训练。重现实验时还需保留原始数据集、镜像和产物文件。

## 当前进度与边界

Phase 1–6 已实现，详见 [Phase 6 验证记录](docs/phase6-report.md)。截图为本地演示运行，包含模拟与 Docker 实验；不能将单次 MNIST 提升理解为通用能力评测。

历史运行对比属于观察性统计，不证明文献策略的因果收益。项目是有边界的研究自动化系统，目前不应宣称已经实现递归自我改进（RSI）。

## 验证

```bash
pytest -q
ruff check src tests
mypy src
cd frontend
npm run build
npm run lint
npm run smoke
```

前端烟雾检查覆盖路由渲染与语言翻译。默认后端测试排除需要 Docker 或真实外部服务的测试。
