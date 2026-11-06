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

这些记录大部分仍是 **catalog-only**。当前第二弹已有 127 张牌通过 `SpiritforgedRules` 执行：

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
- `SFD-046-221` Poro Snax：入场抽 1；支付 Energy 与 Calm、横置并摧毁自身后再抽 1。
- `SFD-052-221` Heart of Dark Ice：横置后通过统一目标窗口给任意单位 +3 Might。
- `SFD-110-221` Fiora, Peerless：单挑战斗中通过统一 Might 计算加倍自身战力。
- `SFD-116-221` Yone, Blademaster：征服无人战场后打开敌方基地单位目标窗口，按自身 Might 造成伤害。
- `SFD-163-221` Deathgrip：有序点选两名友方单位，消灭第一名、按其 Might 临时增益第二名并抽 1。
- `SFD-166-221` Rally the Troops：结算时抽 1，并在本回合后续友方单位进入时自动给予增益。
- `SFD-168-221` Vanguard Armory：横置后连续选择三个合法目的地，生成三个 Recruit token。
- `SFD-028A-221` Lucian, Gunslinger alternate print：复用 Lucian 的 Assault 与攻击触发。
- `SFD-089A-221` Rumble, Scrapper alternate print：复用 Mech +1 Might 与 Hold 生成 Mech。
- `SFD-149A-221` Ezreal, Prodigy alternate print：复用弃 1 抽 2 的入场选择窗口。
- `SFD-003-221` Blood Rush：通过统一单位目标窗口给予单位本回合 Assault 2。
- `SFD-017-221` Sudden Storm：点选战场单位造成 2 点伤害；若目标正在攻击则造成 4 点。
- `SFD-040-221` Thwonk!：只提供正在攻击的单位作为目标，并将其眩晕。
- `SFD-041-221` Apprentice Smith：移动到战场后公开查看牌库顶，Gear 进入手牌，其他牌统一回收。
- `SFD-070-221` Wages of Pain：点选战场单位造成 3 点伤害，并生成横置 Gold Gear。
- `SFD-100-221` Yordle Explorer：监听已完成出牌事件，打出 Power cost 至少 2 的牌时抽 1。
- `SFD-104-221` Petricite Monument：作为临时 Gear 给予己方单位 Deflect，并在下个己方开始阶段按 Temporary 规则移除。
- `SFD-123-221` Corrupt Enforcer：移动到战场后通过统一弃牌窗口弃 1；赢得战斗后抽 1。
- `SFD-151-221` Bonds of Strength：Reaction，有序点选两名友方单位，各获得本回合 +1 Might。
- `SFD-181-221` Mechanized Menace：注册为 Legend 全局能力，使己方 Mech 在防守时获得 Shield。
- `SFD-171A-221` Renata Glasc alternate print：复用衍生物入场就绪规则。
- `SFD-227-221` / `SFD-227-STAR-221` Ahri, Inquisitive：复用战斗指定阶段的敌方单位目标窗口并给予 -2 Might。
- `SFD-235-221` / `SFD-235-STAR-221` Yasuo, Windrider：复用统一移动计数，在本回合第三次移动时得分。
- `SFD-236-221` / `SFD-236-STAR-221` Darius, Executioner：有前一张已完成出牌时入场就绪，并为同战场的其他友方单位提供 +1 Might。
- `SFD-237-221` / `SFD-237-STAR-221` Karma, Channeler：复用 Vision 与所有回收事件的目标触发路径。
- `SFD-240-221` Mechanized Menace alternate print：复用 Legend 全局 Shield 能力。
- `SFD-242-221` Glorious Executioner：复用战斗胜利后的 Legend 抽牌监听。
- `SFD-055-221` Needlessly Large Yordle：注册 Shield 5、Tank，以及本回合 Hold 得分带来的费用减免。
- `SFD-223-221` / `SFD-223-STAR-221` Vayne, Hunter：注册 Assault 3、对手控制战场时入场就绪，征服后确认付费回手。
- `SFD-230-221` / `SFD-230-STAR-221` Teemo, Strategist：Hidden 与防守时五张公开查看/回收、按 Hidden 数量伤害复用同一窗口。
- `SFD-232-221` / `SFD-232-STAR-221` Sett, Brawler：入场/征服增益与“消耗增益获得 +4”使用统一注册能力动作。
- `SFD-185-221` Glorious Executioner：普通印刷接入 Legend 战斗胜利抽牌监听。
- `SFD-105-221` Ruin Runner：以共享目标免疫谓词从敌方的单位法术和能力目标窗口中排除。
- `SFD-204-221` On the Hunt：Signature 法术通过统一 ready helper 使己方单位全部待命。
- `SFD-110A-221` Fiora, Peerless alternate print：复用单挑战斗加倍 Might 计算。
- `SFD-233-221` / `SFD-233-STAR-221` Yone, Blademaster：复用征服无人战场后的基地伤害目标窗口。
- `SFD-044-221` Legion Quartermaster：出牌动作中明确点选并回收一个友方 Gear 作为额外费用。
- `SFD-004-221` Bushwhack：Hidden 关键词复用现有暗置路径；结算后本回合后续友方单位入场就绪，并生成横置 Gold Gear。
- `SFD-122-221` Called Shot：结算时打开牌库顶两张的公开选择窗口，玩家抽取一张，另一张通过统一回收事件置于牌库底。
- `SFD-132-221` Beast Below：入场后打开有序双目标窗口，必须选择另一名友方单位与一名敌方单位并分别回到物主手牌。
- `SFD-138-221` Windsinger：Hidden 单位入场后先确认是否发动，再点选战场上 Might 不超过 3 的单位回手。
- `SFD-126-221` Loyal Pup：防守触发通过共享战斗窗口确认是否从基地移动到防守战场。
- `SFD-128-221` Overzealous Fan：防守触发先确认是否牺牲自身，再点选攻击方单位并将其回基地。
- `SFD-189-221` / `SFD-244-221` Fire Below the Mountain：Legend 的 Reaction 资源能力接入统一资源动作，在反应窗口横置并加入一枚 Rainbow 法力。
- `SFD-192-221` Shurelya's Requiem：出牌后的全体友方单位就绪通过统一 Gear 入场触发处理。
- `SFD-020-221` / `SFD-020A-221` Draven, Vanquisher：战斗胜利生成横置 Gold Gear，并在攻击/防守触发时通过可选窗口支付法力获得本回合 +2 Might。
- `SFD-196-221` Defiant Dance：Reaction 通过共享多目标窗口依次点选两名不同单位，确认后分别给予本回合 +2 与 -2 Might。
- `SFD-194-221` Counter Strike：Reaction 点选单位后设置本回合下一次伤害预防标记并抽 1，法术/能力伤害与战斗伤害共用该标记。
- `SFD-013-221` Blast Corps Cadet：可选支付额外 Energy 与 Fury 后，入场触发通过共享目标窗口点选战场单位并造成 2 点伤害。
- `SFD-067-221` Frostcoat Cub：可选支付额外 Mind 符文后，入场触发通过共享目标窗口点选单位并给予本回合 -2 Might。
- `SFD-083-221` Hextech Anomaly：Reaction 资源转换动作允许玩家选择支付 1 至全部 Rainbow power，并获得等量 Energy。
- `SFD-117-221` Ancient Henge：Reaction 资源转换动作允许玩家选择支付 1 至当前全部 Energy，并获得等量 Rainbow power。

它们通过命名空间化的 `CardSetRegistry` 注册，使用现有普通打出、目标支付、结算链和关键词计算路径。目标型扩展法术使用注册表声明的目标规格，和 Origins 的鼠标点选/确认窗口共用一条路径。其余 SFD 卡牌仍会被明确拒绝为 `RulesUnavailable`，不会从规则文本自动猜测效果。装备附着、Repeat、复杂衍生物和多步骤替代效果继续保持 catalog-only。

最小测试方式：

```python
import json
from riftbound.spiritforged import SpiritforgedRules

deck = json.load(open("examples/spiritforged-cluster.json", encoding="utf-8"))
rules = SpiritforgedRules([deck, deck])
```
