# 第一弹扩展开发日志

更新时间：2026-10-27（Asia/Shanghai）。本文件用于服务中断、对话中断或 agent 交接时恢复工作。

## 当前基线

- 规则依据：RUP5（2026-10-09），官方卡牌归档提交 `a330ca8325ae792548660b1ccef0e7dd97062bd7`。
- 当前分支：`simulator`。
- 当前规则实现版本仍为 `origins-subset/0.3.0`。
- 第一弹目录有 298 张基础编号：142 unit、84 spell、30 gear、24 battlefield、12 legend、6 rune。
- 目前显式执行 226 张；其余 72 张在构筑时拒绝，不会静默当作白板。

## 本轮已完成

### 显式效果处理器注册表

新增 `riftbound.effects.EffectRegistry`。Origins 后端把当前 7 类结算链效果
（单位触发、移动触发、洞察/弃牌决策和法术）逐一注册，再由结算链按名称分发。
处理器必须返回是否已完成；返回未完成会保留决策窗口并暂停结算链。未知效果、重复
注册或返回非布尔完成状态都会立即报错，不会静默按白板处理。后续扩展可以在独立
处理器中加入新机制，再把触发窗口和替代效果接入同一注册表。

### Fury/Mind 构筑簇

新增 OGN-003 Chemtech Enforcer（Assault 2、入场弃 1）和 OGN-088 Mega-Mech，
并加入 OGN-247 Daughter of the Void 的 40 张合法示例套牌。新增的单张弃牌决策
也通过效果注册表进入结算链；GUI/CLI 可使用 `daughter` 变体复现这组资源与触发。

### 基础伤害与静态单位簇

继续加入 OGN-005、029、085、093、095、105、114、201、229 等法术，覆盖多目标伤害、
减益、条件抽牌、无目标抽牌、全手牌重置和直接击杀；加入 Draven、Ahri、Shield、
单独作战与基础白板单位。所有新增牌均有回归测试和本地卡图，复杂的装备、Hidden、
Deathknell 与需要新选择窗口的入场触发仍保持拒绝。

### 结算日志与交接信息

`Environment` 新增派生 `event_log`。每个成功动作记录：动作序号、动作参数、动作前后阶段、行动权、分数、战场控制、结算链、待排序触发、战斗状态和效果选择状态。事件日志进入审计回放，重放后必须一致；它不进入玩家观察，避免把调试信息泄漏给策略。

GUI 底部日志现在有序号，并显示回合玩家、当前行动玩家、当前阶段、战斗战场、待排序触发、结算链（顶到低）和等待中的决策。链上日志只显示可公开的效果摘要。

### 卡池清点

主要缺口集中在装备/永久物、Hidden/reveal、反制、牌区移动、动态触发/替代效果、分割伤害和复杂多目标选择。Deathknell、Stun、Tank、Shield、部分传奇和战场已经有基础实现；机制计数摘要见 `docs/card-pool-expansion.md`。

### 严格规则修正

伤害分配已按 RUP5 467.2.c.3–467.2.c.4 修正：选择一个目标后先分配到致死；存在其他可分配单位时停止；没有其他单位时自动把剩余强制过量伤害继续分配到当前目标。待同时结算的伤害会显示在单位卡下方。

### 目标选择与 Stun 基础层

加入私有目标选择窗口：只有拥有行动权的玩家能看到合法目标，选择完成后才继续
结算链。OGN-234 Harnessed Dragon、OGN-051 Solari Shieldbearer 和 OGN-082
Whiteflame Protector 使用该窗口。单位新增本回合 Stun 状态；Stun 单位不产生战斗
伤害，回合结束清除。装备区目前只有 `core.py` 的通用 GearZone 原语和单元测试，尚未
接入 Origins 对局的完整装备牌区。GearZone 已按 RUP5 148.1.a.1、149.1、149.2 和
359.2.d 修正：非特殊效果下只能进入控制者的 Base，并且进入时 Ready/竖置。
GUI 也把对手 Base 放回对手手牌与身份区一侧；我方 Base 保留在我方区域下方。

随后加入 Rune Prison、Discipline、Cannon Barrage、Flurry of Blades 和 Primal
Strength，复用目标选择、Stun、反应时机和战场范围伤害窗口。

本轮继续加入 Sky Splitter、En Garde、Find Your Center、Confront、Morbid Return
和 Grand Strategem。Confront 的后续单位 Ready 状态会在回合开始时清除；Morbid
Return 在结算链中选择弃牌区单位，目标选择不会提前泄漏给对手。

本轮补入传奇 Herald of the Arcane（OGN-265）：在主阶段支付 1 点能量并横置传奇，
在控制者基地生成 1 Might Recruit 单位衍生物。该主动能力复用现有传奇资源动作与
Recruit token 原语，并加入能量、横置和生成位置回归测试。
同时补入 Nine-Tailed Fox（OGN-255）的攻击替代效果：敌方攻击者进入由该传奇控制的
战场时获得本回合 -1 Might，最低仍为 1；该修正复用本回合临时力量层并加入战斗窗口测试。
Relentless Storm（OGN-249）也加入了可选的 `legend_channel` 动作：本回合打出
Mighty 单位后可横置传奇，从符文牌库顶端横置引导一枚符文；机会不会跨回合保留。

本轮继续补入基础单位与法术簇：Sunlit Guardian（OGN-054）和 Lecturing Yordle
（OGN-087）加入 Tank/Shield 与入场抽牌，Watchful Sentry（OGN-096）加入 Deathknell
抽牌，Stormclaw Ursine（OGN-137）加入入场引导，First Mate（OGN-132）和 Pit Rookie
（OGN-136）加入入场目标选择。Stand United、Last Stand、Consult the Past、Retreat、
Gust、Rebuke、Hidden Blade 和 Facebreaker（OGN-053/069/083/104/169/172/213/220）
已接入抽牌、Temporary、回手、击杀和同战场 Stun 结算。所有卡图通过官方归档导入器
生成并纳入 `card_images.json`。

本轮补入 6 张可执行战场：Back-Alley Bar（OGN-277）在单位离开该战场时给予本回合
1 Might；Grove of the God-Willow（OGN-280）持有时抽 1；Startipped Peak（OGN-288）
持有时引导 1 枚横置符文；Vilemaw's Lair（OGN-295）禁止单位从该战场移动回基地；
The Arena's Greatest（OGN-290）在每名玩家首次开始阶段给予 1 点；Zaun Warrens
（OGN-298）征服时弃 1 再抽 1。后三类触发接入统一的 hold/conquer
计分入口；移动限制在合法移动生成阶段生效。Zaun Warrens 当前在无选择窗口的场景中按
手牌顺序弃牌，后续若接入通用弃牌选择窗口应替换为显式玩家选择。Startipped Peak
的“may channel”现已进入可选效果确认窗口。

新增法术中带 Hidden 的牌（OGN-053、OGN-213、OGN-220）当前只执行其公开 Action
侧；Hidden 的隐藏、揭示和反应时机仍记录为未完成机制，不会被假装成完整支持。

后续法术批次加入 Charm（OGN-043）、Mobilize（OGN-134）和 Ride the Wind（OGN-173）。
Charm/Ride the Wind 使用显式目的地选择并按移动规则横置或准备单位；Mobilize 在符文牌库
有牌时引导一枚耗竭符文，牌库为空时抽一张。法术移动后的 Showdown 现已通过统一移动
结算函数自动开启。

本轮同步加入 Vayne、Crackshot Corsair、Soaring Scout、Leona 和 Shen
（OGN-035/130/216/238/241），覆盖 Assault、攻击触发伤害、Deathknell 引导、Shield
和 Tank。攻击触发牌在多个合法敌方目标时当前取第一个目标，待通用攻击触发选择窗口
接入后改为显式选择。

同时加入 Altar to Unity、Navori Fighting Pit 和 Void Gate
（OGN-275/283/296）：持有时生成 Recruit、给首个未 Buff 友军加 Buff，以及让法术/能力
对该战场单位的每次伤害增加 1。Navori 的可选目标目前取首个未 Buff 友军，待统一选择
窗口接入后改为玩家确认。

本轮机制簇继续加入 Blind Monk、Unforgiven、Radiant Dawn、Bounty Hunter 和 The Boss
（OGN-257/259/261/267/269）；传奇动作覆盖 Buff、跨基地移动和临时 Ganking，Radiant
Dawn 在 Stun 后自动 Buff 首个友军，The Boss 当前只实现征服后准备传奇的部分。
同时加入 Bandle Tree、Fortified Position、Hallowed Tomb、Monastery of Hirana、
Obelisk of Power、Reaver's Row、Reckoner's Arena、Sigil of the Storm、Targon's Peak、
The Candlelit Sanctum、The Dreaming Tree 和 The Grand Plaza
（OGN-278/279/281/282/284/285/286/287/289/291/292/293）。其中尚未迁移到统一选择
窗口的复杂效果仍可能采用首个合法目标或自动路径，并已在测试与交接记录中标明；Recruit DE/NX/Sprite 衍生物
（OGN-271/272/274）也已纳入卡图与构筑禁止校验。

本轮把移动、可选效果和目标选择收拢为统一窗口。普通移动、Charm、Ride the Wind、
Unforgiven 以及其他效果移动现在共用移动结算函数，移动到会产生冲突的战场后会自动
进入 Showdown；Reaver's Row 和 Fortified Position 会在战斗前要求选择并确认目标。
Startipped Peak、Bandle Tree、Hallowed Tomb、Obelisk of Power、The Grand Plaza 等
可选效果会暂停正常行动，由对应玩家在底部栏确认或跳过；同一玩家同时得到多个可选
效果时，先明确触发顺序再逐项处理。Singularity 与 Back to Back 增加了点选多目标、
显式确认的交互路径，底部状态栏会持续显示目标窗口、可选队列和结算链。

本轮修正了目标选择时机：Dangerous Duo 的目标在能力进入结算链前选择，Retreat 支持直接
点击手牌后选择目标或取消打出并恢复费用/手牌/链状态；Ravenbloom Student 的“when you
play a spell”按 RUP5 383.3/383.4 作为独立触发链项处理。符文区新增连续资源操作回撤，
任何其他动作或跳过时点都会关闭回撤窗口。

Ahri, Inquisitive（OGN-119）的 Attack/Defend Trigger 现按 RUP5 466.2.c–d、383.4.e/f
在获得攻击者或防守者身份后进入目标选择窗口，再作为独立链项结算；底部日志会记录
触发加入链、目标选择、战力/伤害/眩晕/位置变化和资源变化。

为便于验收，新增 `complex` 合法 Fury/Mind 试验套牌，集中包含 Legion、Buff、Vision、
Deathknell、Assault、Reaction、Singularity 和 Reaver's Row 等已完成机制，可通过 GUI
变体或 CLI 导出。单位卡下方现在显示横置/就绪、当前战力、临时战力增减、伤害、待分配
伤害、Buff、眩晕、Assault、Shield、Ganking 和临时单位标记；这些标记直接来自引擎状态。

新增 `complex_test_deck()` 试验卡组及 `--variant complex` 图形界面入口。该合法
Daughter of the Void（Fury/Mind）套牌集中放入 Legion、Buff、Vision、Deathknell、
Assault、Reaction、Singularity 和 Reaver's Row 等已完成机制，便于手动回归复杂结算。

同一批次补入低复杂度单位与法术：OGN-016/037/074/078/079/084/086/103/118/119、
OGN-125/139/151/164/165/218/225/240/243/246/161/174/185/195/239，以及
OGN-048/123/128/138/146/209/252/260/262/266/270。范围覆盖 Legion/Assault、
Shield/Tank、Vision、Deathknell、Recruit 生成、目标 Stun、简单伤害、抽牌、准备和移动。
OGN-185 的移动弃牌、OGN-174 的开放战场、OGN-252 的征服回手及部分多目标选择仍采用
简化路径，具体限制已留在对应测试与代码注释中。

## 本轮新增规则审计与卡池

- 按 RUP5 350.1、351.2、158.3/158.3.a 修正 Ravenbloom Student：法术完成结算后才生成其触发；若学生在法术结算中离场，则不生成触发。Darius 的“第二张牌”在法术场景也沿用该结算后窗口。
- 按 RUP5 403.2、403.4 将已执行的单位入场目标触发统一为“触发最终化时选择目标”：Harnessed Dragon、Solari Shieldbearer、Whiteflame Protector、First Mate、Pit Rookie、Cemetery Attendant、Solari Chief，以及新增 Riptide Rex、Blastcone Fae、Zaunite Bouncer、Maddened Marauder。没有合法目标的触发会从链上移除。
- 按 RUP5 383.4.e/f、466.2.c–d 将 Crackshot Corsair 和 Leona, Determined 的攻击触发加入战斗链并要求目标选择，移除原先自动选择第一个敌方单位的路径。
- 新增 10 张显式卡牌：Poro Herder、Riptide Rex、Sprite Call、Blastcone Fae、Gemcraft Seer、Sprite Mother、Thousand-Tailed Watcher、Zaunite Bouncer、Maddened Marauder、Teemo, Scout；支持集扩展到 168 张，并为每张加入官方卡图与回归测试。
- 新增 Yasuo, Remorseful、Viktor, Innovator、Fight or Flight、Fading Memories、Kog'Maw, Caustic、Miss Fortune, Buccaneer；支持攻击触发、对手回合触发、Deathknell、临时单位和开放战场规则。
- 建立 Origins GearZone 基础：Gear 只能进入控制者基地，默认竖置；状态进入公开观察和牌张守恒校验。接入 21 张装备，其中 6 种领域资源 Gear、Energy Conduit、Iron Ballista、Sun Disc、Ravenborn Tome、Scrapheap 和 Forge of the Future 已有可执行基础路径。
- 新增 Kadregrin、Eclipse Herald、Tasty Faefolk、Portal Rescue、Dr. Mundo、Ekko 和 Spoils of War，覆盖 Mighty 抽牌、Stun 触发、Deathknell、回收重播和基础抽牌。
- 新增 Convergent Mutation、Unyielding Spirit、Carnivorous Snapvine、Overt Operation、Volibear, Imposing、Undercover Agent、Kayn, Unleashed、Yasuo, Windrider，覆盖临时防护、双目标战斗、移动计数和更多 Deathknell。
- 新增 Thermo Beam 与 Acceptable Losses，接入 Gear 区域的全局清除效果；装备目标能力和更复杂的替代效果仍记录为后续机制工作。
- 新增 Mask of Foresight、Solari Shrine、Garbage Grabber，并接入单人战斗增益、击杀眩晕单位触发和 Gear 资源回收动作。
- 将 Fortified Position（OGN-279）纳入正式支持集；其防御触发与战斗护盾路径已有回归覆盖。
- 新增 Raging Soul、Vi、Sona、Pit Crew、Herald of Scales，覆盖弃牌状态、回收资源、回合结束符文、Gear 触发和 Dragon 费用静态修正。
- 新增 Shakedown、The Harrowing、Salvage 的基础目标/弃牌区/抽牌路径；Shakedown 的“对手选择抽牌或承受伤害”仍需独立选择窗口。

## 尚未完成

- 第一弹 298 张尚未全部执行。当前支持集已扩展到 226 张，完整扩展需要按机制层逐步增加处理器和回归测试。

### 当前未完成项目清单

- 当前仍未接入的单位（47）：OGN-002、006、018、019、020、026、031、034、036、041、044、056、067、068、070、073、091、107、111、112、113、121、135、140、141、147、150、155、157、162、167、177、192、194、196、199、200、202、208、226、230、231、235、236、271、272、274。
- 当前仍未接入的法术（27）：OGN-008、025、033、045、057、062、064、071、080、115、122、156、183、187、198、203、221、224、237、244、248、250、254、256、258、264、268。
- 当前仍未接入的装备（6）：OGN-023、077、101、160、227、242；GearZone 基础、资源 Gear 和部分主动能力已经可用，但这些牌需要替代效果、Hidden 或复杂牌库选择。
- 当前仍未接入的传奇/战场/衍生物（2+1+3）：OGN-263、OGN-278，以及 OGN-271/272/274。OGN-279 Fortified Position 已纳入支持集。
- 这些卡牌当前会被构筑校验拒绝；它们不会作为无效果白板进入对局。剩余机制集中在反制、Hidden/reveal、控制权、复杂牌区选择、额外费用、替代效果、分割伤害和多模式能力。
- 当前事件日志是派生调试记录，不是完整裁判级事件溯源；仍需要独立官方裁判或第二套引擎做差分验证。

## 下一步顺序

1. 在效果注册表上继续实现通用 `event/effect/choice/replacement` 数据结构和事件窗口，不按 253 张牌继续堆叠 `if code == ...`。
2. 按机制簇扩展：基础 Action/Reaction → 牌区移动与选择 → Stun/Deathknell → Hidden/装备 → Tank/Shield/Prevent → 动态战场与控制权。
3. 每个机制簇新增真实卡牌回归测试、随机对局和回放测试。
4. 每次扩展后更新本文件、`docs/rules-coverage.md`、支持卡表和分发包。
