# Riftbound Origins 自动对战模拟器

Python 3.12+，支持双人自动对战、自博弈样本和确定性回放。**0.3.0 可运行一个明确限定的 Origins 卡池；尚不支持完整 Origins。**

规则依据：用户提供的 RUP5（2026-10-09）。卡牌、标签及已知勘误来自本仓库 `archive-download` 分支的固定官方来源归档（a330ca8）。运行时完全离线，无需模型、API 密钥、GPU 或额外下载卡图；当前支持牌的缩略卡图已随模拟器打包，源码树还包含完整高清悬浮图。

- **代码分支**：[simulator](https://github.com/sstmminer/riftbound/tree/simulator)
- **小型下载包**：[riftbound-simulator-0.3.0.zip](https://github.com/sstmminer/riftbound/raw/refs/heads/simulator/downloads/riftbound-simulator-0.3.0.zip)
- **图形界面**：运行 `python -m riftbound gui`，支持卡图、符文区、点击、右键菜单、拖拽、动态战场、底部结算/目标/可选效果窗口和高清悬浮预览；`--variant vision` 可直接演示 Vision。
- **下载、安装和测试攻略**：[docs/quickstart-zh.md](docs/quickstart-zh.md)
- **158 张可执行卡牌**：[docs/supported-cards.md](docs/supported-cards.md)
- **规则覆盖与限制**：[docs/rules-coverage.md](docs/rules-coverage.md)
- **扩展开发日志与交接记录**：[docs/development-log.md](docs/development-log.md)

## 快速开始（macOS / Linux）

```bash
git clone --depth 1 --branch simulator https://github.com/sstmminer/riftbound.git
cd riftbound
python3.12 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m riftbound simulate --games 3 --seed 42 --output artifacts/first-run
.venv/bin/python -m riftbound replay artifacts/first-run/replay-0000.json
```

Windows 命令见下载测试攻略。输出目录必须不存在或为空；重复运行请选择另一个目录。

## 当前功能

- 合法 40 张主牌库（含天选英雄）、12 枚符文、3 个备选战场；默认双方使用同一副合法套牌。
- 调度、先后手、回合开始/结束、重置、引导、抽牌与 Burn Out。
- 显式符文支付、传奇资源能力、单位出牌、Accelerate、Legion、Buff、Assault、Shield、Deflect、Ganking 及支持列表内卡牌效果。
- 响应链后进先出、触发顺序选择、合法时机、失效目标、Showdown、分组移动、伤害分配、同时伤害、死亡/治疗/撤回、控制权、征服/据守和最后一分。
- 统一移动结算：普通与效果移动共用校验，移动到冲突战场自动衔接 Showdown；多目标法术支持逐张点选并显式确认，可选效果支持确认/跳过与同时触发顺序。
- 卡牌与符文守恒、不变量校验；非法动作不改变状态；固定种子、状态克隆及逐步回放哈希。
- 随机和贪心基准策略；可选导出按玩家视角标记的 JSONL 决策记录。

所有效果由显式处理器执行，不使用 LLM 判牌，不执行卡面中的代码。目录里存在某张牌不意味着能够执行它；自定义套牌必须通过支持范围和构筑合法性检查。

## Python 接口

```python
from riftbound.engine import Environment
from riftbound.origins import OriginsRules
from riftbound.policies import GreedyPolicy
from riftbound.training import self_play

env = Environment(OriginsRules(), max_steps=3000)
episode = self_play(env, (GreedyPolicy(), GreedyPolicy()), seed=42)
print(episode.terminated, episode.truncated, episode.rewards)
```

也可用 `reset(seed=...)`、`observe(player)`、`legal_actions()`、`step(action)`、`clone()` 接入策略。奖励向量按玩家编号排列；下一行动玩家可能连续行动，不能假定双方严格轮流。`Environment()` 不指定后端时仍拒绝启动，防止把有限卡池误当成通用完整规则引擎。

## 训练与数据边界

本版适合验证自博弈管线、设计策略接口和有限卡池实验，尚未经过独立裁判或官方实现的差分验证。它不是完整 Riftbound 训练环境或竞技强度评测器。Gymnasium/PettingZoo 适配、固定向量编码、并行采样和神经网络训练器尚未提供。

`replay-*.json` 是含随机种子及双方动作的特权审计文件，不能作为策略输入。`decisions-*.jsonl` 含双方各自的私有观测；训练时只能使用每条记录标注玩家的当时观测，不拼接对手或未来信息。步数截断不是真实平局。Python 对象接口不是恶意策略代码沙箱。

卡牌数据和游戏商标权利归 Riot Games 及其权利人；本项目不代表官方，也不授予相关素材再许可。
