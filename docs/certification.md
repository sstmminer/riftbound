# Origins 完整认证门

`tools/full_certification.py` 是完整认证的入口。它把四类证据合并为一个 JSON 报告：

1. 298 张 Origins 目录的哈希、编号和支持表分区；
2. `AbilityRegistry` 的来源卡牌、横置能力和动作处理器完整性；
3. 固定种子对局、无动作死锁、步数截断和 Replay 一致性；
4. 尚未完成的规则差分阻塞项。

运行：

```bash
python tools/full_certification.py \
  --seeds 3 \
  --output artifacts/origins-certification.json
```

工具会在存在未关闭阻塞项时返回非零退出码。即使 298 张卡牌都出现在 `SUPPORTED`，也不会因此把它们标记为完整认证；`catalog_partition` 和 `ability_registry` 只证明结构完整，`checks.certified` 还要求所有规则差分阻塞项关闭。

当前阻塞项包括：缺少独立第二套规则裁判、复杂跨区域控制权和嵌套免费打出、AbilityRegistry 的递归复制与部分替代效果、以及少数战场可选效果的完整交互矩阵。因此当前报告应诚实地保持 `certified=false`，直到每项都有规则场景、实现和回归测试。

稳定性门可以单独运行：

```bash
python tools/stable_baseline.py \
  --seeds 10 \
  --output artifacts/stable-baseline.json
```

稳定性门通过只表示已覆盖执行路径没有检测到死锁、截断或回放漂移，不等同于完整 Origins 裁判认证。
