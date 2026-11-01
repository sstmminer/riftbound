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

这些记录大部分仍是 **catalog-only**。当前第二弹已有 65 张牌通过 `SpiritforgedRules` 执行：

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
- `SFD-027-221` Dunebreaker：手牌不超过两张时入场就绪，Hold 后抽 2。
- `SFD-061-221` Aspiring Engineer：入场后从弃牌区点选 Gear 回手；
- `SFD-062-221` Bubble Bot：入场后从友方 Mech 中点选另一张并就绪。
- `SFD-152-221` Eminent Benefactor：Hold 后生成两个横置 Gold Gear；
- `SFD-171-221` Renata Glasc, Industrialist：己方衍生物入场时就绪；
- `SFD-174-221` Trove Golem：入场后生成四个横置 Gold Gear。
- `SFD-098-221` Sea Monkey：出牌时可额外支付 1 点法力，支付后获得增益。
- `SFD-032-221` Disarming Rake：入场时先确认是否发动，再点选并摧毁任意 Gear；
- `SFD-035-221` Guardian of the Passage：Hold 时确认是否从弃牌区点选一张单位或 Gear 回手；
- `SFD-038-221` Ribbon Dancer：移动到战场后，通过同一目标窗口点选另一名友方单位并给予增益；
- `SFD-039-221` Royal Entourage：入场结算时由玩家选择将己方 Legend 横置或待命；
- `SFD-071-221` Breakneck Mech：Mech 共享 Deflect、Ganking，并按现有入场条件进入待命；
- `SFD-091-221` Buhru Captain：入场先确认是否发动，再选择抽牌或给自身增益；
- `SFD-149-221` Ezreal, Prodigy：入场打开弃牌选择，完成弃牌后抽两张；
- `SFD-157-221` Royal Guard：入场生成 2 Might 的 Sand Soldier 衍生物；
- `SFD-162-221` Blood Money：通过统一战场单位目标窗口点选 2 Might 以下单位，按其控制者生成 Gold；
- `SFD-175-221` Undertitan：入场给予其他友方单位本回合 +2 Might；
- `SFD-179-221` Corinna Veraza：从战场移动时在目的地生成三个 Recruit 衍生物。
- `SFD-065-221` Forecaster：己方 Mech 共用 Vision 牌库顶查看窗口；
- `SFD-069-221` Plundering Poro：征服时生成横置 Gold Gear；
- `SFD-074-221` Pickpocket：入场时可确认并摧毁 Energy 不超过 1 的 Gear，随后生成横置 Gold Gear；
- `SFD-075-221` Prize of Progress：己方 Gear 激活能力成功使用时获得本回合 +1 临时战力。
- `SFD-031-221` Desert's Call：在己方基地生成 Sand Soldier；
- `SFD-034-221` Feral Strength：Reaction，点选单位获得本回合 +2 战力；
- `SFD-066-221` Frigid Touch：Reaction，点选单位获得本回合 -2 战力；
- `SFD-076-221` Production Surge：控制 Mech 时 Energy 减 2，生成 3 Might Mech token 并抽 1。
- `SFD-007-221` Gem Jammer：入场时通过统一触发目标窗口给一张单位本回合 Ganking；
- `SFD-021-221` Ferrous Forerunner：Deathknell 生成两个 3 Might Mech token；
- `SFD-089-221` Rumble, Scrapper：己方 Mech 获得 +1 静态战力，Hold 时生成 Mech token。
- `SFD-012-221` Battering Ram：按本回合已完成出牌数减费，最低 Energy 1；
- `SFD-015-221` Perched Grimwyrm：仅能打到本回合已征服的战场；
- `SFD-093-221` Dauntless Vanguard：可打到有敌方单位占据的战场；
- `SFD-158-221` Sandshifter：入场时点选并消灭 Might 不超过 3 的敌方单位。
- `SFD-014-221` Minotaur Reckoner：在场时阻止单位移动到基地；
- `SFD-060-221` Tianna Crownguard：在战场时阻止对手通过 Hold/Conquer 得分；
- `SFD-131-221` Ancient Warmonger：Accelerate，并按战场敌方单位数获得动态 Assault。
- `SFD-028-221` Lucian, Gunslinger：Assault 1；攻击时通过战斗触发目标窗口对敌方单位造成 Assault 伤害。

它们通过命名空间化的 `CardSetRegistry` 注册，使用现有普通打出、目标支付、结算链和关键词计算路径。目标型扩展法术使用注册表声明的目标规格，和 Origins 的鼠标点选/确认窗口共用一条路径。其余 SFD 卡牌仍会被明确拒绝为 `RulesUnavailable`，不会从规则文本自动猜测效果。签名牌 `SFD-204 On the Hunt` 暂缓注册，因为其合法套牌还依赖尚未执行的 Sivir/Battle Mistress 组合；装备附着、Repeat、Hidden、复杂衍生物和多步骤替代效果也继续保持 catalog-only。

最小测试方式：

```python
import json
from riftbound.spiritforged import SpiritforgedRules

deck = json.load(open("examples/spiritforged-cluster.json", encoding="utf-8"))
rules = SpiritforgedRules([deck, deck])
```
