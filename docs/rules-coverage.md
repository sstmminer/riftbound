# 规则覆盖与已知限制（0.3.0）

目标：双人标准构筑，487 的 1v1 Duel 单局。卡牌范围见 [supported-cards.md](supported-cards.md)。目录 298 张不等于可执行 298 张。

## 固定来源

- 用户提供的 `RiftboundCoreRulesRUP5_En_EN.pdf`，142 页，更新于 2026-10-09。来源元数据和 SHA-256 见 [rules-source.json](rules-source.json)。PDF 不随轻量下载包分发；云工作区缓存位于忽略路径 `artifacts/rules/`。
- 官方来源归档：本仓库 `archive-download` 分支提交 a330ca8325ae792548660b1ccef0e7dd97062bd7。基础印刷编号逐一存在，保存的 raw_record 与官方 HTML 快照逐条一致；本次接入时核对过来源哈希。
- [origins-source.json](../riftbound/data/origins-source.json) 固定原始 cards.json、errata.json 和归一化数据的哈希。已关联的修订文本优先，原文本与 errata_check_incomplete 状态保留。
- 支持表中的卡图来自同一官方归档提交，缩略图映射见 `riftbound/data/card_images.json`；完整原图归档不随轻量包分发。
- 公开图鉴 1,408 条与元数据 1,416 条的差额原因仍未知；另有 Unleashed 的 LeBlanc 未关联勘误。这些不是已经确认的 Origins 基础编号缺失，不能据此宣称官方全球卡池完整性。

## 执行覆盖

| 机制 | 条款 | 状态与范围 |
| --- | --- | --- |
| 构筑与开局 | 103、111–118、487 | 双人、领域、同名上限、天选英雄、符文、三个战场选择、随机先手与战场 |
| 调度 | 117、417.5 | 最多两张；先补牌，再随机顺序回收到牌库底 |
| 回合 | 315–317、487.7 | 重置、据守、引导、抽牌、Main、结束；后手首次额外符文 |
| 资源与费用 | 164、167、135.2.e、357、445 | 显式横置/回收、传奇 Add、能量/领域力量、加速和 Deflect；原子支付 |
| 出牌 | 337.2、349–359 | 单位立即入场；法术进入链；单位只能到基地或己方控制战场 |
| 响应与触发 | 311–313、327–348、382–403 | 后进先出、连续让过、Focus、触发前目标选择、己方同时触发顺序选择；可选效果进入确认队列；限支持牌 |
| 移动 | 144、447–460 | 单次/组移动、共同目的地、Ganking；选择分步输入，提交时同时移动和横置；效果移动共用结算函数并在冲突战场自动进入 Showdown |
| 战斗 | 142、461–468 | Showdown、攻击/防守修正、先分配后同时造成、致命先于治疗、撤回攻击者、战后控制 |
| 得分与终局 | 469–474、487 | 征服/据守、每战场每玩家每回合一次、最后一分替代抽牌、领先才胜利 |
| 抽空牌库 | 414、432 | 回收弃牌、对手得分、继续抽牌、空弃牌重复 Burn Out 即时终局 |
| 卡牌效果 | 支持表 | 271 张显式处理器，含基础伤害、减益、抽牌、目标选择、Stun、攻击触发、静态单位、基础 Gear 资源和六种基础符文；Singularity/Back to Back、Kinkou、Albus 支持点选多目标并显式确认；Wildclaw、Jinx、Karma 进入统一事件链，Burn Out 和 Vision 顶牌回收也会触发 Karma；Sabotage、Dr. Mundo、Forge of the Future 使用公开展示/选择窗口（Sabotage 的展示结束与选择权均在施放者一侧）；Hidden、Karthus Deathknell、Noxian Guillotine、Mushroom Pouch、Swift Scout 已加入；未支持卡牌开局前拒绝 |
| Gear 基础原语 | 148.1、149、359.2.d | `core.GearZone` 已验证只进控制者 Base 且进入 Ready；具体 Origins Gear 牌区尚未接入 |
| 隐藏信息 | 107.3、108、128、422、811 | 手牌仅本人可见，牌库顺序双方不可见；Hidden facedown 区支持单卡占位、下回合 0 费打出、控制方正面查看与对手牌背显示；Noxus Saboteur 会阻止对应战场的对手揭示/打出，Bandle Tree 允许第二张，Tideturner 适用异地目标例外 |

通用模块测试使用合成元数据；真实 Origins 卡牌与完整游戏测试在 tests/test_origins.py。三张无主动效果的战场分别调整胜利分数、单位力量、Ganking，相关效果同时作用于双方。

## 当前不支持

其余 Origins 卡牌、其他系列、多局 Match、多人模式、Hidden/装备/Deathknell/法术反制/控制权改变等不在注册卡池内的交互。代码不尝试根据自然语言猜测效果，也不静默跳过未知关键词。

测试通过只证明已执行的场景及不变量，没有官方裁判或另一套独立引擎的差分认证。当前训练文件用于有限卡池实验，不代表完整 Riftbound。Greedy 与 Random 只是基准策略，不代表竞技水平。

回放规则 ID 绑定引擎语义版本、数据和双方套牌；改变处理器语义应升级版本。CLI 还检查 Python 主/次版本，回放逐步验证状态与随机数哈希。局面克隆和种子仅供特权训练/搜索代码使用，不应泄漏给只允许玩家观测的策略。
