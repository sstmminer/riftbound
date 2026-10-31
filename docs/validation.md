# 本地验证记录

版本：0.3.0。日期：2026-10-31（Asia/Shanghai）。环境：Linux，Python 3.12.14。Windows/macOS 尚未在本机执行；仓库配置了 Windows/Linux 的 Python 3.12 CI，远端执行状态需以 GitHub Actions 为准。

- `python -m unittest discover -s tests -q`：368 项通过。
- `python -m unittest tests.test_cross_region_interactions tests.test_gui_decision_prompts tests.test_gui_interactions tests.test_gui_layout tests.test_ownership_audit tests.test_spell_expansion_new tests.test_next_cards tests.test_gear_batch tests.test_battlefield_next tests.test_engine tests.test_mystic_rechoices tests.test_reveal_windows -q`：100 项跨区域、嵌套结算、回收触发、战场可选效果、目标窗口和 GUI 日志专项测试通过。
- `PYTHONPATH=. python tools/check_batch.py --seeds 3`：6 局真实支持卡池对局（贪心、随机各 3 局），6 局正常终局，0 截断，6 份逐步回放校验通过。
- 批量测试实际执行了单位/法术出牌、资源支付、同时触发排序、分组移动、响应让过和伤害分配等动作；机器可读结果见 [batch-validation.json](batch-validation.json)。
- CLI 的状态、支持表、套牌生成/校验、样本导出、输出防覆盖、截断识别、回放与篡改拒绝均有测试。
- 支持表中的 Origins 卡牌/符文缩略图、横置卡图和牌背资源均通过本地文件检查；法术和战场牌没有横置图是预期情况。Tk 窗口在无显示的云工作区未直接启动，GUI 模块导入与打包资源检查通过。
- 引擎事件日志包含动作前后公开状态摘要，并通过回放一致性测试；摘要会记录结算链、可选效果队列和目标选择窗口。
- `complex` Fury/Mind 试验套牌通过构筑校验，并完成贪心策略 1v1 烟雾测试；目标时机、Ravenbloom、Ahri Attack/Defend 独立触发和符文回撤均有回归测试。

这些结果验证当前有限卡池及场景，不构成全 Origins 规则覆盖、独立裁判认证或训练策略质量证明。合成框架测试和真实 Origins 对局测试在不同测试文件中明确区分。

分发验证：构建 wheel 后，在独立虚拟环境从本地 wheel 无索引安装，在仓库目录之外运行状态、完整一局和回放校验均通过；解压后应再次运行 368 项测试。

### 稳定基线门（2026-11-01）

基线命令为：

```bash
python tools/stable_baseline.py --seeds 10 --output artifacts/stable-baseline.json
```

该工具先运行完整单元测试，再用固定种子分别执行贪心和随机策略，逐步检查动作合法性、非终局状态是否仍有合法动作，并对每局动作记录做回放校验。报告中的 `deadlocks` 只统计非终局且没有合法动作的状态；`repeated_states` 是语义状态重复的诊断计数，不会单独判定失败，因为符文回收后的 `undo_rune` 可以合法回到先前状态。`truncated` 表示达到步数上限，属于基线失败信号。

报告字段 `full_origins_supported` 当前为 `false`：本门验证的是现有 Origin 运行路径的稳定性，不宣称已经完成全部卡牌的裁判级差分认证。只有在测试、无死锁、无截断、逐局回放均通过时，报告的 `gate.passed` 才为 `true`。

最近一次单种子烟雾结果：368 项测试通过，贪心/随机各 1 局均正常终局，0 死锁、0 截断、2/2 回放校验通过；随机局记录 27 次语义状态重复，均来自可逆符文操作。
