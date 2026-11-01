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

这些记录大部分仍是 **catalog-only**。当前第二弹已有 28 张牌通过 `SpiritforgedRules` 执行：

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
- `SFD-036-221` Lonely Poro：Deathknell，在该战场没有其他友方单位时抽 1；
- `SFD-048-221` Stellacorn Herder：移动后抽 1；
- `SFD-094-221` Direwing：控制另一条 Dragon 时入场就绪；
- `SFD-106-221` Show of Strength：Reaction，按己方 Mighty 单位数量抽牌；
- `SFD-147-221` Downwell：将所有单位与 Gear 按物主回手；
- `SFD-001-221` Against the Odds：Reaction，点选战场上的友方单位，按该处敌方单位数量获得临时战力；
- `SFD-005-221` Detonate：点选 Gear，将其摧毁并让控制者抽 2；
- `SFD-097-221` Punch First：点选单位，获得本回合 +5 临时战力；
- `SFD-135-221` Factory Recall：点选任意 Gear 回到其物主手牌；
- `SFD-155-221` Honest Broker：Deathknell，生成横置 Gold Gear 衍生物。
- `SFD-047-221` Simian Ancestor：受到增益后就绪；
- `SFD-072-221` Dropboarder：控制至少两个 Gear 时入场就绪；
- `SFD-130-221` Treasure Hunter：移动后生成横置 Gold Gear 衍生物；
- `SFD-137-221` Harpoon Squad：从战场移动时获得本回合 +2 临时战力；
- `SFD-159-221` Trusty Ramhound：有另一名友方单位同处时获得 +1 静态战力；
- `SFD-167-221` Unsung Hero：若死亡时为 Mighty，Deathknell 抽 2。

它们通过命名空间化的 `CardSetRegistry` 注册，使用现有普通打出、目标支付、结算链和关键词计算路径。目标型扩展法术使用注册表声明的目标规格，和 Origins 的鼠标点选/确认窗口共用一条路径。其余 SFD 卡牌仍会被明确拒绝为 `RulesUnavailable`，不会从规则文本自动猜测效果。签名牌 `SFD-204 On the Hunt` 暂缓注册，因为其合法套牌还依赖尚未执行的 Sivir/Battle Mistress 组合；装备附着、Repeat、Hidden、复杂衍生物和多步骤替代效果也继续保持 catalog-only。

最小测试方式：

```python
import json
from riftbound.spiritforged import SpiritforgedRules

deck = json.load(open("examples/spiritforged-cluster.json", encoding="utf-8"))
rules = SpiritforgedRules([deck, deck])
```
