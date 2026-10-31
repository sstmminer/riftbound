# Origins 完整认证初审

这份清单用于区分“已进入构筑/执行集”和“已经完成裁判级行为认证”。`SUPPORTED` 中的 298 张卡牌全部可被目录、构筑校验和状态模型识别，但这项事实本身不代表每张卡牌的所有触发、替代效果和跨区域交互都已经验证。

## 初审结果

对 `riftbound/data/origins.json` 的 298 张牌与 `riftbound/origins.py`、`riftbound/support.py` 进行静态交叉检查后，以下卡牌需要优先建立独立行为场景：

| 卡牌 | 需要认证的行为 | 初审状态 |
| --- | --- | --- |
| OGN-063 Spirit's Refuge | 入场选择友军并给予增益；被增益友军获得 Deflect | 未发现完整的入场目标窗口/静态 Deflect 差分场景 |
| OGN-118 Wraith of Echoes | 每回合第一次友军死亡抽牌 | 未发现独立死亡事件回归场景 |
| OGN-143 Pirate's Haven | 友军变为就绪时给予本回合 +1 Might | 未发现独立 ready 事件回归场景 |
| OGN-162 Miss Fortune, Captain | Accelerate、Ganking；每回合第一次移动后可选择 ready 其他单位 | 未发现完整移动后可选 ready 场景 |
| OGN-178 Undercover Agent | Deathknell：弃 2 后抽 2 | 未发现独立 Deathknell 选择场景 |
| OGN-192 Mindsplitter | 入场时选择对手、公开手牌并选择一张弃置 | 未发现完整公开手牌/选择弃置窗口场景 |
| OGN-228 Vanguard Helm | 增益友军死亡后选择另一友军并给予增益 | 未发现死亡后目标选择场景 |

OGN-001/010 的 Accelerate、OGN-135 的 Hidden、OGN-274 的 Temporary 由通用机制处理，仍需在认证报告中保留专门回归场景；它们不应因为没有卡号字面分支而被判定为未实现。

## 认证门要求

完整认证不能只检查 `SUPPORTED == catalog`。每张卡至少需要：

1. 正常施放/入场或触发的正向场景；
2. 目标离场、控制权改变、反制或资源不足时的负向场景；
3. 与回收、死亡、Hidden、装备、复制能力和结算链嵌套的组合场景（若卡面涉及）；
4. 固定种子回放记录，并验证公开日志、内部事件日志和最终状态一致。

在上述场景全部通过前，稳定性门可以报告“无卡死、可回放”，但不应将 `full_origins_supported` 标记为 `true`。

