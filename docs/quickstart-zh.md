# 下载、安装和测试攻略

本攻略针对 **0.3.0 / simulator 分支**。它能自动运行内置的合法 Origins 套牌及所列 67 张卡牌；尚未实现完整 Origins。包含本地图形界面，也可用命令行查看状态和生成对局文件。

## 1. 下载

选择一种方式即可：

- [小型 ZIP](https://github.com/sstmminer/riftbound/raw/refs/heads/simulator/downloads/riftbound-simulator-0.3.0.zip)：解压后进入 `riftbound-simulator` 文件夹。
- [GitHub 代码页](https://github.com/sstmminer/riftbound/tree/simulator)：确认分支是 `simulator`，再选择 Code → Download ZIP，解压进入项目根目录。
- 已安装 Git：`git clone --depth 1 --branch simulator https://github.com/sstmminer/riftbound.git`，然后 `cd riftbound`。

仓库默认的 `archive-download` 是大型卡牌资料归档，不能代替模拟器代码分支。本模拟器不需要下载原图、SQLite 或完整资料归档。

ZIP 校验值在同目录 [SHA256SUMS.txt](https://github.com/sstmminer/riftbound/blob/simulator/downloads/SHA256SUMS.txt)。Windows 用 `Get-FileHash .\riftbound-simulator-0.3.0.zip -Algorithm SHA256`；Linux 用 `sha256sum`，macOS 用 `shasum -a 256`，与文件内的值比较。

## 2. 安装 Python 和项目

推荐安装 **Python 3.12**；项目要求 3.12 或更新版本，当前 CI 配置验证 3.12。第一次安装需要联网下载 Python 构建工具，后续运行完全离线。不需要 GPU、模型或 API 密钥。

在项目根目录打开终端。Windows 可以在资源管理器地址栏输入 `powershell` 后回车。无需执行虚拟环境激活脚本或修改执行策略。

Windows PowerShell：

```powershell
py -3.12 --version
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m riftbound status
```

macOS / Linux：

```bash
python3.12 --version
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m riftbound status
```

状态应包含 `catalog_cards: 298`、`executable_cards: 67`、`supported_subset_playable: true` 和 `full_origins_supported: false`。

## 3. 启动图形界面

在项目根目录运行：

```bash
python -m riftbound gui
```

默认使用 starter 体验套牌。要演示包含 Mystic Poro 的 Vision/洞察交互，运行 `python -m riftbound gui --variant vision`；运行 `python -m riftbound gui --variant daughter` 可测试 Daughter of the Void、Kai'Sa、Chemtech Enforcer 和六域资源簇。窗口顶部也可以切换套牌并点击“重新开始”。战场数量由规则状态和卡牌效果决定，界面会自动显示新增战场。

Windows 将 `python` 换成 `.\.venv\Scripts\python.exe`，macOS/Linux 换成 `.venv/bin/python`。窗口包含传奇区、英雄区（规则中的 Champion Zone）、动态战场区、两个基地/手牌、弃牌区、放逐区和公开状态区。

- 点击或右键手牌/己方单位打开合法操作菜单；符文左键横置，右键选择回收。
- 单位和符文横置后会切换为横向卡面，恢复就绪后回到竖向卡面。
- 将手牌拖到基地或任意战场执行出牌。自己的主要阶段中，左键单位可选择/多选，金色边框表示已选；把已选单位拖到同一合法基地或战场后会自动完成移动并横置。
- 休眠单位不能被选择；如果最新选择与已有选择没有共同合法目的地，选择会被拒绝，右侧消息栏会说明原因。
- 洞察（Vision）会弹出选择窗口，可选择保留牌顶或回收到牌库底。
- 对手使用内置贪心策略自动行动；只显示其公开区域和手牌数量。
- 当前窗口使用默认体验套牌和 2 个随机战场；引擎支持动态追加战场，尚未开放多玩家模式。

当前支持牌和符文均使用随包附带的官方来源缩略卡图显示，不需要另外下载图片。

如果 Linux 的 Python 没有 Tk 支持，Debian/Ubuntu 通常需要安装与当前 Python 版本对应的 `python3-tk`（例如 `sudo apt install python3-tk`）；Windows 官方 Python 和 macOS 通常已自带 Tk。

关闭窗口即可结束当前进程；对局不会自动保存，需用 CLI 的 `simulate --output` 生成可验证回放。

## 4. 运行测试

Windows：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
$LASTEXITCODE
```

macOS / Linux：

```bash
.venv/bin/python -m unittest discover -s tests -v
```

应看到所有测试通过，最后显示 `OK`，退出码 0。测试包括通用规则、真实卡牌效果、响应链、信息隔离、整局自动对战、回放和 CLI。测试中的合成游戏仅验证框架；真实后端的测试在 `tests/test_origins.py`。

## 5. 自动打三局

Windows：

```powershell
.\.venv\Scripts\python.exe -m riftbound simulate --games 3 --seed 42 --output artifacts/first-run
.\.venv\Scripts\python.exe -m riftbound replay artifacts/first-run/replay-0000.json
```

macOS / Linux：

```bash
.venv/bin/python -m riftbound simulate --games 3 --seed 42 --output artifacts/first-run
.venv/bin/python -m riftbound replay artifacts/first-run/replay-0000.json
```

默认双方使用贪心基准策略和同一副合法套牌。每局自动进行调度、支付、出牌、响应、移动、战斗与得分。终端显示步数、回合数、比分和获胜玩家；玩家编号为 0 和 1。Aspirant's Climb 会提高胜利分数，因此可能需要 9 或 10 分获胜。

`artifacts/first-run` 中包含：

- `summary.json`：胜场统计及每局结果。
- `replay-0000.json` 等：含种子、套牌、动作及逐步状态校验值的审计回放。

回放验证应返回 `verified: true`。它重放并校验每一步，不只是比较最终胜负。请使用相同 Python 主/次版本和代码/卡牌版本；后续更改结算实现后，旧回放不保证兼容。

输出目录必须不存在或为空，程序不会覆盖既有对局。重复测试请换成 `artifacts/second-run` 等新目录。

## 6. 随机策略和步数截断

将上述模拟命令改为：

```text
python -m riftbound simulate --games 10 --seed 100 --policy random --max-steps 3000 --output artifacts/random-run
```

这里的 `python` 应替换成虚拟环境解释器路径。`terminated: true` 表示规则终局；`truncated: true` 表示达到步数上限。截断不算平局或胜利，不能作为正常终局回报训练。

## 7. 导出实验训练样本

```text
python -m riftbound simulate --games 3 --seed 42 --export-decisions --output artifacts/training-run
```

额外生成 `decisions-0000.jsonl` 等文件。每行包含行动玩家、该玩家当时的观测、合法动作、所选动作、最终奖励和终局/截断标志。当前是带结构字段的 JSON，不是固定长度张量；需由训练侧编码。

审计回放含种子，可推断隐藏牌序，不得作为策略输入。决策文件混合双方各自的私有观测，训练时必须按记录中的玩家视角使用；不能把双方手牌或未来记录拼接输入。奖励向量按玩家编号排列，不能假定下一行动玩家一定是对手。

## 8. 查看卡牌和改套牌

```text
python -m riftbound catalog --supported
python -m riftbound deck --output my-deck.json
python -m riftbound validate-deck my-deck.json
python -m riftbound simulate --deck0 my-deck.json --deck1 examples/starter-deck.json --output artifacts/custom-run
```

编辑 `my-deck.json` 的基础编号和数量。主牌库包含天选英雄实体，默认恰好 40 张；每个卡名最多 3 张，符文恰好 12 张，备选战场 3 个不同名称。还需满足领域身份和英雄标签。衍生物不能放入主牌库，目录中的未支持卡牌也不能用于对局。

不要用 Windows PowerShell 5 的默认 `>` 重定向来保存套牌 JSON，可能生成 UTF-16；使用上面的 `deck --output` 命令生成 UTF-8。

## 常见问题

- **找不到 Python**：安装 Python 3.12，或将创建环境命令换成实际解释器路径。
- **No module named riftbound**：确认位于项目根目录，且使用安装该项目的 `.venv` 解释器。
- **Unsupported Origins cards**：卡牌尚未实现；从支持表选择，不要删掉检查或忽略效果。
- **输出目录不为空**：改用新目录，原数据会保留。
- **回放版本不符或哈希不符**：使用生成该回放时的代码、数据与 Python 版本；不要修改校验值让它通过。
- **卡牌费用看起来不一致**：`energy` 是能量，`power_cost` 是领域力量费用，`might` 是单位力量；三者不同。
- **运行结果并非每局相同胜利分数**：两个战场随机选取，可能同时具有提高胜利分数的效果。

本版还没有独立裁判对照测试、全卡池支持或竞技强度保证。它已经可以验证有限卡池的自动对局与训练管线，扩展卡池时应逐张添加处理器和回归测试。
