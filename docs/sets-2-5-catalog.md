# 第二至第五弹卡库

`riftbound/data/expansions.json` 是从固定的公开卡牌快照导入的目录数据。当前包含：

| 代码 | 卡组 | 记录数 |
| --- | --- | ---: |
| OGS | Proving Grounds | 24 |
| SFD | Spiritforged | 288 |
| UNL | Unleashed | 288 |
| VEN | Vendetta | 237 |
| RAD | Radiance | 219 |
| 合计 |  | 1056 |

每条记录保留官方 print ID、公开编号、类型、领域、费用、战力、规则文本、勘误状态和图片 URL。包含 promo、star/alternate print 等公开记录时，目录 ID 使用规范化后的官方 print ID，例如 `SFD-227-STAR-221`，不会与普通印刷版本冲突。

导入来源和哈希记录在 `riftbound/data/expansions-source.json`。可用以下命令重新生成：

```bash
python tools/import_expansion_catalog.py \
  --git-ref origin/archive-download
```

查看一个扩展卡组：

```bash
python -m riftbound catalog --set SFD
```

这些记录大部分仍是 **catalog-only**。当前第二弹已有第一批 12 张牌通过 `SpiritforgedRules` 执行：

- `SFD-006-221` Eager Drakehound：入场时就绪；
- `SFD-037-221` Navori Scout：Deflect；
- `SFD-096-221` Laurent Bladekeeper：Ganking；
- `SFD-156-221` Laurent Duelist：Assault 2；
- `SFD-176-221` Xin Zhao, Vigilant：Tank，并按卡面条件入场就绪；
- `SFD-087-221` Premonition：Reaction，抽 3；
- `SFD-222-221` Seal of Rage：横置后产生 Fury 符能；
- `SFD-226-221` Seal of Focus：横置后产生 Calm 符能；
- `SFD-229-221` Seal of Insight：横置后产生 Mind 符能；
- `SFD-231-221` Seal of Strength：横置后产生 Body 符能；
- `SFD-234-221` Seal of Discord：横置后产生 Chaos 符能；
- `SFD-238-221` Seal of Unity：横置后产生 Order 符能。

它们通过命名空间化的 `CardSetRegistry` 注册，使用现有普通打出、目标支付、结算链和关键词计算路径。其余 SFD 卡牌仍会被明确拒绝为 `RulesUnavailable`，不会从规则文本自动猜测效果。每张后续牌需要先注册统一的能力/效果实现，并补充目标窗口、资源支付、替代效果和回归场景后，才能加入可执行集合。

最小测试方式：

```python
import json
from riftbound.spiritforged import SpiritforgedRules

deck = json.load(open("examples/spiritforged-cluster.json", encoding="utf-8"))
rules = SpiritforgedRules([deck, deck])
```
