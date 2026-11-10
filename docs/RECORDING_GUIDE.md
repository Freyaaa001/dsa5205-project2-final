# 真实运行录屏指引（给持有数据快照的同学）

## 为什么要录

课程对视频的第一条评分要求是 “Show an end-to-end run (data build → fit → validation → out-of-sample with costs)”。现有视频里这一段是用幻灯片重现的终端输出，而且只覆盖“测试、出图表、编译报告”，因为原始数据不在做视频的那台电脑上。我们需要一段**真实的屏幕录制**来替换它。

录好后不用自己剪辑，把文件发回即可，剪辑和配音由合成脚本完成。

## 准备（约 10 分钟）

在一个新文件夹里克隆带演示脚本的分支，再把你本机已有的数据目录链接进来。这样不会改动你原来的工作目录，也不会碰冻结的快照。

```bash
git clone --branch freya/video-and-report-polish https://github.com/Freyaaa001/dsa5205-project2-final.git demo
```

把分支克隆到名为 `demo` 的新文件夹。

```bash
cd demo && python3.13 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt
```

进入文件夹，建虚拟环境并安装固定版本的依赖。

```bash
mkdir -p runs/snapshots && ln -s /你的原工作目录/runs/snapshots/team34_nextclose10_v2 runs/snapshots/team34_nextclose10_v2
```

把已构建好的快照链接进来。请把 `/你的原工作目录` 换成真实路径。

```bash
ln -s /你的原工作目录/data data
```

可选。把基础数据目录也链接进来。有了它，演示会真实跑一遍“数据构建”这一步，输出写到新的 `runs/snapshots/demo_时间戳`，不覆盖原快照。没有它，脚本会跳过构建并说明使用现成快照。

## 录制

1. 终端窗口调成 16:9，大约 1600×900。字号调到 18 以上，深色背景，先 `clear` 清屏。
2. 关掉消息通知。**不要让 `data/` 里的个股文件内容入镜**，脚本本身不会打印它们。
3. 开始录屏。macOS 按 `Cmd+Shift+5` 选“录制所选窗口”。Windows 按 `Win+Alt+R`。
4. 运行下面这一条命令，等它走完，再停止录屏。

```bash
bash scripts/demo_run.sh
```

这条命令会依次执行并在屏幕上打印每一步的真实命令：

| 步骤 | 做什么 |
|---|---|
| 0 | 打印 Python 版本、依赖版本、当前提交 |
| 1 | 数据构建：对齐的日频面板和十区间标签（需要 `data/`） |
| 2 | 重建六个基本面信号，跑 2022 验证期和 2023–2025 评估期的组合，扣除成本 |
| 3 | 打印结果表，并与仓库里随附的日收益逐日对账，显示最大差异 |
| 4 | 回归测试 |
| 5 | 重新生成报告的表、图和收益归因 |
| 6 | 编译报告 PDF（本机装了 LaTeX 才会执行） |

运行多久都没关系，合成时会自动加速，并在画面角落标注“真实录屏”和加速倍数。

## 讲不讲解都可以

- **不出声**：最省事。合成脚本会配上解说，并把录屏加速到和解说一样长。
- **自己讲解**：录屏保持原速，声音原样保留。这种情况下建议整段控制在 3 分钟以内，可以在步骤 2 等待时讲解时间顺序和防泄漏的做法。

## 发回什么

1. 录屏文件，MP4 或 MOV 都可以。
2. 终端里最后三屏的文字输出，复制成文本即可。主要是步骤 3 的结果表和“max |daily net return difference|”那两行。
3. 如果任何一步报错，把完整报错发回来，不要自己改脚本硬跑。

## 需要说明的限制

- 步骤 1 到 3 依赖数据，写这份指引的电脑上没有数据，所以**这三步没有被实测过**。命令本身与 `README.md` 里的一致。步骤 0、4、5、6 已实测通过。
- 最终策略本身不做模型拟合。如果想把“拟合”也录进去，可以在一个**新的输出目录**里重跑原主实验的筛选和训练，单独录成第二个文件。这两条命令同样未在本仓库实测，耗时可能很长：

```bash
PYTHONPATH=src .venv/bin/python -m usq.project2.screen --database runs/snapshots/team34_nextclose10_v2 --output runs/demo_models
```

因子筛选，生成训练用的设计矩阵。

```bash
PYTHONPATH=src .venv/bin/python -m usq.project2.models --database runs/snapshots/team34_nextclose10_v2 --output runs/demo_models
```

按半年扩展窗口训练 Ridge、Lasso、XGBoost，并在 2022 年上做验证选择。**不要把输出指向已冻结的主实验目录。**

## 收到录屏后怎么剪进视频

把文件放到 `video/clips/run.mp4`（该目录不进 git），需要配音时把解说写到同名的 `video/clips/run.txt`，然后：

```bash
cd video && python3 build_video.py --redo 16,17 --clip-after 15=clips/run.mp4
```

只重渲染改过的幻灯片，其余片段复用，录屏插在第 15 页之后。
