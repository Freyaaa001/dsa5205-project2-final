# 最终研究入口与复现

正式报告是`reports/final/Group_34_Report.pdf`，可编辑源文件为同目录的`Group_34_Report.tex`。进度和待办只记在`Project2_最终版进度.md`。历史讨论方案、完整研究Notebook及冻结结果保留，均不覆盖。

## 精简后的主线

最终候选为六基本面方向固定的排名评分，Top100、buffer150、十日换仓、平方根市值配置、2%单股目标上限、单边10bps。它是观察历史后的研究提名，不是仅由2022选出的盲测冠军；不再调整它来追求更高评价收益。

| 文件 | 职责 |
|---|---|
| `configs/project2_final.json` | 输入路径、组合常量和回溯提名说明 |
| `configs/project2_final_signals.json` | 独立入口所需的冻结信号定义、方向及共同样本约束 |
| `src/usq/project2/final_study.py` | 唯一最终研究入口：六因子重算、信号合成、组合重放和汇总 |
| `src/usq/project2/factors.py` | 共享因子定义、截面回归、WQ算子及超预期事件 |
| `src/usq/project2/research_portfolio.py`、`ledger.py` | 共享缓冲选股、权重和交易账本 |
| `scripts/verify_final_study.py` | 独立排名重放、会计核查、历史对照及冻结文件检查 |
| `scripts/build_final_report_assets.py` | 从实际结果生成LaTeX表格与矢量图 |

历史`exploration.py`、`deep_dive.py`和`late_fusion.py`属于完整实验档案。最终候选的独立重跑不需要它们的历史输出。保留这些文件是为了可追溯性，而不是要求展示者逐个运行。

## 环境

从仓库根目录执行，使用Python 3.13及`requirements-project2.txt`中的已验证版本：

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements-project2.txt
```

以下命令用`PYTHONPATH=src`，无需全局修改Python路径。XGBoost在macOS可能需要libomp；纯最终候选不调用XGBoost拟合。数据目录及`runs/`不加入公开仓库。

## 最小重跑：只依赖数据快照

本机已存在`runs/snapshots/team34_nextclose10_v2`。若从干净目录和同一已补齐的基础数据快照开始，先运行：

```bash
PYTHONPATH=src .venv/bin/python -m usq.database.close_labels \
  --source data --output runs/snapshots/team34_nextclose10_v2
```

`data/`必须是提供方有权使用的同一基础研究快照，包含`panels/`和`metadata/`；不是任意CSV目录。此步骤拒绝覆盖已有输出。公开数据的替换不能保证同样的历史股票池、会计映射和数值结果；代码不假装能自动恢复缺失的WRDS导出规则。

重算最终候选及必要基准：

```bash
PYTHONPATH=src .venv/bin/python -m usq.project2.final_study \
  --standalone --output runs/project2_final_standalone_v1
```

此入口从快照重算六基本面及三条WQ的可观察性，不读取历史因子缓存、训练矩阵或预测。WQ仅保持共同样本约束，不进入基本面评分。输出14个组合：两阶段的三种基本面权重及三种匹配池基准，加评价期20/30bps压力。75个快照文件按实际内容校验。

主结果：`portfolios/fundamental_sqrt_cap/evaluation/daily.csv`；总表：`portfolio_summary.csv`；提名依据：`final_strategy.json`；核查：`audit/verification.json`。本机独立入口的14份日账本与完整最终研究逐项一致，记录在完整运行的`audit/standalone_comparison.json`。

## 完整精简研究：代表性对照

若已有原主实验、扩展探索、延后财务及后融合档案，运行：

```bash
PYTHONPATH=src .venv/bin/python -m usq.project2.final_study
PYTHONPATH=src .venv/bin/python scripts/verify_final_study.py
```

默认输出`runs/project2_final_v1`，包含38组合。最终候选、权重、成本、延后、消融及融合重新回测；Ridge和扩展量价模型复用历史已审计预测。Lasso/XGBoost仅保留原冻结A/B汇总，明确为继承对照。没有把“重新回测”写成“全部重新训练”。

改动协议或输入请指定新的`--output`；不完整缓存会被完成标记与哈希检查拒绝。完整研究仍含所有必要负面证据，额外探索网格留在原档案中。

## 报告生成

`results/project2_final/`包含约4.2MB的汇总数据和策略级日收益，供图表与报告重建；不含个股原始行情、预测或持仓。生成报告图表不再依赖完整`runs/`研究档案。

```bash
PYTHONPATH=src .venv/bin/python scripts/build_final_report_assets.py
cd reports/final
TEXINPUTS=./tex-support: pdflatex -interaction=nonstopmode -halt-on-error Group_34_Report.tex
TEXINPUTS=./tex-support: pdflatex -interaction=nonstopmode -halt-on-error Group_34_Report.tex
```

两次编译用于目录和交叉引用。TeX模板缺少的两个包以原始CTAN源码置于`tex-support/`；不修改系统TeX。原模板原样存为`report-template.original.tex`。英文报告沿用模板11pt字体、A4、0.82英寸页边距、navy配色和页眉；第一页含Abstract，第二页独立目录，总20页。图表由真实CSV生成，报告正文不放执行待办、缓存清理或团队同步记录。

报告`Group_34_Report.pdf`已逐页渲染检查。学号与实际分工仍按用户要求留空，不能把该空白解释为已经完成的成员贡献声明。
