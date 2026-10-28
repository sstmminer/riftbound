# 本地验证记录

版本：0.3.0。日期：2026-10-28（Asia/Shanghai）。环境：Linux，Python 3.12.14。Windows/macOS 尚未在本机执行；仓库配置了 Windows/Linux 的 Python 3.12 CI，远端执行状态需以 GitHub Actions 为准。

- `python -m unittest discover -s tests -q`：167 项通过。
- `PYTHONPATH=. python tools/check_batch.py --seeds 3`：6 局真实支持卡池对局（贪心、随机各 3 局），6 局正常终局，0 截断，6 份逐步回放校验通过。
- 批量测试实际执行了单位/法术出牌、资源支付、同时触发排序、分组移动、响应让过和伤害分配等动作；机器可读结果见 [batch-validation.json](batch-validation.json)。
- CLI 的状态、支持表、套牌生成/校验、样本导出、输出防覆盖、截断识别、回放与篡改拒绝均有测试。
- 支持表中的 216 张卡牌/符文缩略图、横置卡图和牌背资源均通过本地文件检查；法术和战场牌没有横置图是预期情况。Tk 窗口在无显示的云工作区未直接启动，GUI 模块导入与打包资源检查通过。
- 引擎事件日志包含动作前后公开状态摘要，并通过回放一致性测试；摘要会记录结算链、可选效果队列和目标选择窗口。
- `complex` Fury/Mind 试验套牌通过构筑校验，并完成贪心策略 1v1 烟雾测试；目标时机、Ravenbloom、Ahri Attack/Defend 独立触发和符文回撤均有回归测试。

这些结果验证当前有限卡池及场景，不构成全 Origins 规则覆盖、独立裁判认证或训练策略质量证明。合成框架测试和真实 Origins 对局测试在不同测试文件中明确区分。

分发验证：构建 wheel 后，在独立虚拟环境从本地 wheel 无索引安装，在仓库目录之外运行状态、完整一局和回放校验均通过；轻量 ZIP 的 SHA-256、CRC 和路径检查通过，解压后应再次运行 167 项测试。
