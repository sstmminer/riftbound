# 第一弹扩展开发日志

更新时间：2026-10-30（Asia/Shanghai）。本文件用于服务中断、对话中断或 agent 交接时恢复工作。

## 当前基线

- 规则依据：RUP5（2026-10-09），官方卡牌归档提交 `a330ca8325ae792548660b1ccef0e7dd97062bd7`。
- 当前分支：`simulator`。
- 当前规则实现版本仍为 `origins-subset/0.3.0`。
- 第一弹目录有 298 张基础编号：142 unit、84 spell、30 gear、24 battlefield、12 legend、6 rune。
- 目前 298 张均已进入显式执行集；复杂效果仍按规则覆盖表中的专用窗口或受限路径处理，不会静默当作白板。

本轮继续加入 OGN-006 Flame Chompers、OGN-062 Reinforce、OGN-122 Time Warp、OGN-200
Twisted Fate 和 OGN-258 Dragon's Rage。新增效果分别覆盖弃牌区可选回场、牌库顶五张展示、
额外回合与放逐、攻击时符文领域分支，以及“先选择移动目标/目的地，再选择目的地上的第二目标”。
这些牌均进入构筑校验、目标窗口和回归测试。
这五张牌的官方缩略图和高清悬浮图已从固定的 `origin/archive-download` 归档导入，图像映射
记录在 `riftbound/data/card_images.json`；后续新增卡牌必须先运行 `tools/import_card_assets.py`。

Mystic Reversal（OGN-080）按 RUP5 751–755 修正：它不是 Counter，不会移除目标法术；结算后
目标法术留在链上并转由 Mystic Reversal 控制者控制，旧目标清空，立即重新打开合法目标窗口，
包括重复目标、成对目标和目的地选择。重新选择不重复支付原出牌费用；真正的 Defy/Wind Wall
Counter 仍按 426.1.a 从链上移除并进入弃牌区。

原先集中在控制法术链、延迟死亡替代、多区域同时选择、复制全部能力、牌库免费打出和分配伤害的
13 张卡牌现已全部登记并接入显式处理器：OGN-023/025/041/077/107/111/112/115/121/160/
194/242/244。后续仍需继续收紧部分复杂效果的裁判级细节，但它们不再以未注册白板形式进入对局。

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

Falling Star（OGN-029）和 Icathian Rain（OGN-248）现在都使用统一的卡牌点击目标窗口。
Falling Star 可按顺序点击同一单位两次，Icathian Rain 可点击六次；点击序列会在临时窗口中
显示编号，确认前可删除单项或清空重选。引擎保留点击顺序并在确认后按该顺序逐次结算伤害。

#### 目标选择设计原则（交接备忘）

凡是效果需要玩家指定场上单位、装备、增益承载单位或移动目的地，GUI 都应先由卡牌点击
发起，再在场上卡图上点击合法目标；右键菜单只负责启动技能或打开目标窗口，不承载长目标
列表。目标窗口必须保留点击顺序，允许规则允许的重复目标，并在确认前提供临时序列、单项
删除和清空重选。多目标、成对目标、目的地目标、装备能力、单位技能和传奇能力共用同一
`decision`/`choose_target` 路径；重复分配效果必须在确认后按序结算。

本轮已迁移：OGN-029/248、低风险单目标法术、成对目标法术、目的地移动法术、OGN-090/124/184
装备能力、Caitlyn/Malzahar 目标技能，以及 Blind Monk、Bounty Hunter、Swift Scout 的目标能力；
Unforgiven 的目标单位与目的地选择、OGN-256 的同战场总战力约束多选、OGN-266/268 的战场点击和 Bullet Time 的 X 选择也已迁移。
仍需专用界面的范围包括 Dragon's Rage 的连续移动目标、可选装备/符文/手牌选择和需要同时
选择多类区域对象的效果；这些效果不得退回为不可审计的长菜单，应继续复用上述窗口原则。

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
- 按 RUP5 107.3、422、811 接入 Hidden 基础流程：己方控制且未占用的战场可支付 1 点万能符能放置 facedown；下回合起可从该区以 0 费打出。观察接口对控制方提供正面卡图，对手只提供牌背；GUI 支持手牌/英雄区右键放置、战场右键打出和控制方悬浮查看。Hidden 目标限制已覆盖 Stand United、Fight or Flight、Hidden Blade、Blastcone Fae 的战场范围；Pakaa Cub 可直接使用基础 Hidden 流程，Noxus Saboteur 只阻止对手在其所在战场揭示/打出，Bandle Tree 支持第二个 facedown 槽，Tideturner 按勘误允许选择其他位置的友军。

- 本轮继续接入 7 张低依赖牌：Mushroom Pouch 在开始阶段检查己方 facedown 并抽牌；Swift Scout 支持支付能量隐藏 Hidden，并把己方 Teemo 从英雄区或战场回手；Noxian Guillotine 设置本回合下次受伤击杀标记，Legion 时立即击杀；Kinkou Monk 在入场时打开最多两个友军的显式多目标确认窗口。Jinx 的弃牌触发已接入显式弃牌决策、Invert Timelines 和 Zaun Warrens 路径；Karthus 会把其控制者的 Deathknell 触发次数加倍。配套补入官方卡图和回归测试，支持集扩展到 277 张。

- 统一可选/事件窗口：Wildclaw Shaman 先进入触发链并确认是否发动，接受后只显示带 Buff 的己方单位，点击目标消耗一个 Buff，再令 Shaman 获得 Buff 并 Ready；Albus Ferros 先确认，再多选带 Buff 的友军，每个目标消耗一个 Buff 并引导一枚耗竭符文。Jinx 的每个弃牌事件只生成一次强制链触发。新增统一 `recycle_cards_to_main` 事件源后，Karma 会响应牌库耗尽时的 Burn Out 回收、Vision 顶牌回收、Stacked Deck、Vi、Garbage Grabber、Ekko 和战场顶部牌回收，并在链上要求选择友军给予 Buff；仍未注册的复杂回收牌会继续保持构筑拒绝。

- 本轮继续扩展 17 个卡池编号：Stormbringer, Volibear（OGN-250）可选择基地友军，对目标战场敌军按该单位 Might 造成伤害后移动；Fox-Fire, Ahri（OGN-256）支持同一战场总 Might 不超过 4 的多目标击杀，并可走 Hidden 流程；Sprite Call、Sprite Mother 现在生成正确的 OGN-274 Sprite 临时衍生物；Guerilla Warfare（OGN-264）可从弃牌区选择最多两张 Hidden 牌回手，并在本回合提供免费用 Hidden 放置；Qiyana, Victorious（OGN-155）在征服后进入可选窗口，由玩家选择抽牌或横置引导符文；Caitlyn, Patrolling（OGN-068）加入横置主动伤害能力与“最后分配战斗伤害”约束；Get Excited!（OGN-008）加入弃牌后按被弃牌能量造成伤害的两阶段目标窗口；Block（OGN-057）加入 Shield 3、临时 Tank 与 Hidden 目标路径；Brazen Buccaneer、Kraken Hunter、Commander Ledros 接入额外成本替代；Malzahar、Adaptatron、Blitzcrank 接入主动/触发技能；Icathian Rain、Bullet Time 接入多目标与 X 符文费用；Tryndamere 的攻击过量伤害计数与 Symbol of the Solari 的战斗平局回基地替代效果已接入；Soulgorger、Spectral Matron 共享弃牌区单位重播窗口，Udyr 加入四选一技能窗口，Party Favors、Whirlwind、King’s Edict 加入玩家选择窗口。OGN-271/272/274 均纳入目录、牌图和构筑排除校验。

- 新增公开牌区事件窗口：Sabotage 会公开对手整手牌。被展示的玩家记录为 `owner`，而施放 Sabotage 的玩家记录为 `opponent`；有合法选择时由施放者选择一张非单位牌并确认回收到对手主牌库，没有合法选择时也由施放者点击“结束展示”（被展示者不能关闭该窗口）。Dr. Mundo 在开始阶段公开自己的弃牌区并允许最多回收 3 张，Forge of the Future 公开双方弃牌区并允许选择最多 4 张。展示卡牌、已选卡牌和结束展示动作都会进入引擎事件日志与 GUI 底部日志。

- Accelerate 按 RUP5 805.1–805.6 作为打出流程中的可选额外费用处理：控制者先声明是否支付，支付窗口允许使用带 Reaction 的 Add-resource 能力（例如横置符文加能量、回收符文加领域符能），完成支付后单位以 Ready 状态进入。交互界面可以在暂停期间以 `pending` 卡片预览单位的位置，但在该选择完成前不开放其他玩家的优先权，也不把它建模成“先横置入场再准备”。该延迟替代效果不触发任何“单位变为 Ready”触发（RUP5 805.6.a）；多领域单位的符能部分可使用其任一领域（135.2.e.6.c）。

## 最新卡池完成批次

本轮完成 Origins 第一弹最后 13 张卡牌：Unlicensed Armory（OGN-023）、Blind Fury（OGN-025）、Volibear, Furious（OGN-041）、Zhonya's Hourglass（OGN-077）、Ava Achiever（OGN-107）、Heimerdinger, Inventor（OGN-111）、Kai'Sa, Evolutionary（OGN-112）、Promising Future（OGN-115）、Teemo, Strategist（OGN-121）、Dazzling Aurora（OGN-160）、Nocturne, Horrifying（OGN-194）、Baited Hook（OGN-242）和 Divine Judgment（OGN-244）。

新增流程覆盖死亡替代、装备主动能力、攻击/防守触发、牌库顶牌展示与选择、免费打出、分配伤害和多区域资源选择。每张卡均导入官方标准图、横置图和高清悬浮图；`tools/check_assets.py` 验证 298 张映射完整。

本批法术审计注记：Blind Fury（OGN-025）公开对手牌库顶牌，由施放者选择并把该物理牌转为施放者控制后免费打出；Promising Future（OGN-115）先由下家选择、再由另一玩家选择，按下家顺序逐张打出，忽略 Energy 但仍检查并支付 Power；Divine Judgment（OGN-244）以两个玩家独立的四区选择窗口完成后才发出回收事件，避免 Karma 在第二位玩家选择期间插入。当前免费打出的复杂目标法术仍通过已有 legacy 目标路径取首个合法目标，待统一 free-play 目标窗口后可改为点选序列；这属于明确记录的受限交互路径，不按白板处理。

本批仍保留两项明确限制：Volibear（OGN-041）现在以五次可重复点击逐点分配 5 点伤害，已能表达任意分配，但没有单独的数字分配面板；Heimerdinger（OGN-111）通过 `AbilityRegistry` 按 `requires_exhaust=True` 自动发现单位、传奇和装备的横置能力，Vi/Udyr 等没有横置符号的能力以及 Nocturne/Zhonya 的非横置替代效果会被排除。Solari Shrine、Mistfall、The Boss 等事件型横置能力也使用同一注册表和事件窗口。Nocturne（OGN-194）的 Ganking 与牌库顶查看窗口均已接入：Vision 查看顶牌时由查看者私下选择放弃或支付一枚 [A]，支付后先放逐该物理牌，再通过普通单位出牌状态机以零费用打出；无可支付符能时不会暴露不可用选项。Teemo 的防守触发只在实际进入防守战斗时生成，不会因从 Hidden 打出就提前触发。

## RUP5/官方勘误与裁判级审计（2026-10-31）

本次联网核对到的权威来源为：[Core Rules RUP5 PDF](https://cmsassets.rgpub.io/sanity/files/dsfx7636/news_live/5c7946f7c3b8c6e0faff85ab6dadc6d2e721ea94.pdf)、[Tournament Rules PDF](https://cmsassets.rgpub.io/sanity/files/dsfx7636/news_live/861752822d217edf37d9febaeaf77a7d924c1bb6.pdf)、[Origins Errata](https://riftbound.leagueoflegends.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/)、[Core Rules Patch Notes](https://riftbound.leagueoflegends.com/en-us/news/rules-and-releases/riftbound-core-rules-patch-notes/) 和 [Radiance Patch Notes/官方裁定](https://playriftbound.com/en-us/news/announcements/core-rules-radiance-patch-notes-effective-october-16-2026/)。官方 Origins 勘误页面解析到 31 个卡名；其中 Dark Child/Highlander 不在本 Origins 298 张目录，Dragon's Rage/Lee Sin 存在目录别名。官方 Radiance 页面明确了“新选择全部重做、目标触发重新触发、pending 项不可选为目标、Negated 与 Ignored 的区别，以及多领域/无领域 Accelerate 的 [C]→[A] 处理”。官方页面同时说明后续 FAQ 仍会追加，因此目前不能声称公开裁判判例库已经完整。

本次审计确认的剩余结算漏洞和受限事项：

- Nocturne 的替代窗口目前只接入 Vision；Reinforce、Blind Fury、Promising Future、Stacked Deck、Baited Hook、Teemo、Dazzling Aurora 等其他牌库查看/展示入口尚未统一接入逐张 replacement queue。
- Blind Fury 会改写对手牌库物理牌的 `owner`，Possession 也把控制者和牌主共用一个 `owner` 字段；跨玩家控制单位的死亡、回手和回收可能进入错误牌区。
- Stealthy Pursuer 的“may 跟随移动”仍自动接受；Targon's Peak 的符文准备时机提前；Candlelit Sanctum、Navori Fighting Pit、Monastery of Hirana、Zaun Warrens 等仍存在取第一张/第一个目标的简化路径。
- Baited Hook、Dazzling Aurora 和部分免费打出法术仍可能绕过完整入场触发或后续目标窗口；多个死亡替代同时存在时仍使用硬编码优先顺序。
- Reaction 型横置能力在 Heimer 路径中仍可能暴露在过宽时机；多个 Heimer 或原生/复制来源同时触发时的顺序还没有完整裁判化。
- 复杂 optional/replacement 嵌套后的 event log/replay、跨区域选择和所有 look/reveal 入口仍缺少独立裁判差分测试。

## 尚未完成

- 第一弹 298 张均已注册并可进入构筑校验；完整规则差分验证、多人模式和训练基准仍未完成。

### 当前未完成项目清单

- Origins 第一弹没有剩余的未注册卡牌编号；`support.py` 与官方卡图映射均覆盖 298 张目录卡。
- 仍需持续完善的是复杂效果的裁判级边界：多区域同时选择、复制全部能力、少数延迟替代效果、免费打出后的后续目标交互，以及与第二套引擎的差分验证。
- OGN-271/272/274 已纳入目录、牌图和构筑排除校验；当前效果生成路径使用 Recruit (ZN) 与 Sprite，Recruit (DE/NX) 尚无独立生成来源。OGN-263 Swift Scout 与 OGN-278 Bandle Tree 已纳入支持集。
- 上述复杂机制不再通过构筑拒绝规避；每张卡都保留显式处理器，无法完全裁判化的分支会在日志和测试中标明受限路径。剩余工作集中在反制、Hidden/reveal 复杂分支、控制权、复杂牌区选择、额外费用、替代效果、分割伤害和多模式能力。已支持的 OGN-147 Wildclaw Shaman 仍把“是否花费 Buff”简化为自动使用首个可用 Buff；OGN-230/235 的多资源/回收触发和部分 Jinx 弃牌来源仍需统一事件窗口。
- 当前事件日志是派生调试记录，不是完整裁判级事件溯源；仍需要独立官方裁判或第二套引擎做差分验证。

## 下一步顺序

1. 在效果注册表上继续实现通用 `event/effect/choice/replacement` 数据结构和事件窗口，不按 253 张牌继续堆叠 `if code == ...`。
2. 按机制簇扩展：基础 Action/Reaction → 牌区移动与选择 → Stun/Deathknell → Hidden/装备 → Tank/Shield/Prevent → 动态战场与控制权。
3. 每个机制簇新增真实卡牌回归测试、随机对局和回放测试。
4. 每次扩展后更新本文件、`docs/rules-coverage.md`、支持卡表和分发包。
