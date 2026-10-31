# 规则覆盖与已知限制（0.3.0）

目标：双人标准构筑，487 的 1v1 Duel 单局。卡牌范围见 [supported-cards.md](supported-cards.md)。Origins 第一弹 298 张均已进入显式处理器；规则覆盖状态和已知限制仍以本表为准。

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
| 资源与费用 | 164、167、135.2.e、357、445、805 | 显式横置/回收、传奇 Add、能量/领域力量、加速和 Deflect；Accelerate 在出牌流程中暂停并允许 Reaction Add-resource 支付；原子支付 |
| 出牌 | 337.2、349–359 | 单位立即入场；法术进入链；单位只能到基地或己方控制战场 |
| 响应与触发 | 311–313、327–348、382–403 | 后进先出、连续让过、Focus、触发前目标选择、己方同时触发顺序选择；可选效果进入确认队列；限支持牌 |
| 移动 | 144、447–460 | 单次/组移动、共同目的地、Ganking；选择分步输入，提交时同时移动和横置；效果移动共用结算函数并在冲突战场自动进入 Showdown |
| 战斗 | 142、461–468 | Showdown、攻击/防守修正、先分配后同时造成、致命先于治疗、撤回攻击者、战后控制 |
| 得分与终局 | 469–474、487 | 征服/据守、每战场每玩家每回合一次、最后一分替代抽牌、领先才胜利 |
| 抽空牌库 | 414、432 | 回收弃牌、对手得分、继续抽牌、空弃牌重复 Burn Out 即时终局 |
| 卡牌效果 | 支持表 | 298 张显式处理器，覆盖基础伤害、减益、抽牌、目标选择、Stun、攻击触发、静态单位、Gear、符文、Hidden、牌库/弃牌区选择、公开展示、反制链和复杂多目标窗口；Falling Star、Icathian Rain、Bullet Time、Mystic Reversal、Dragon's Rage 等保留有序目标/重选窗口；其中 Falling Star/Icathian Rain 按 2026-01-14 Spiritforged FAQ 作为普通多目标法术处理，不创建 Reflexive Trigger；Promising Future、Blind Fury、Dazzling Aurora、Baited Hook 等牌库选择效果进入统一 reveal/play 流程；复杂替代效果、复制能力和部分跨区域选择仍按开发日志中的受限路径处理。 |
| Gear 基础原语 | 148.1、149、359.2.d | Origins Gear 区已接入，装备只能进入控制者 Base，默认 Ready；已覆盖的装备能力仍受支持表与开发日志中的复杂互动限制 |
| 隐藏信息 | 107.3、108、128、422、811 | 手牌仅本人可见，牌库顺序双方不可见；Hidden facedown 区支持单卡占位、下回合 0 费打出、控制方正面查看与对手牌背显示；Noxus Saboteur 会阻止对应战场的对手揭示/打出，Bandle Tree 允许第二张，Tideturner 适用异地目标例外 |

通用模块测试使用合成元数据；真实 Origins 卡牌与完整游戏测试在 tests/test_origins.py。三张无主动效果的战场分别调整胜利分数、单位力量、Ganking，相关效果同时作用于双方。

## 当前限制

Origins 第一弹卡牌编号已全部注册；Dazzling Aurora/Nocturne 的停止与放逐判例按 [Origins FAQ](https://riftbound.leagueoflegends.com/en-us/news/rules-and-releases/riftbound-origins-faq) 执行；其他系列、多局 Match、多人模式仍不支持。Heimerdinger 通过统一 `AbilityRegistry` 复制所有已注册且明确需要横置的单位、传奇和装备能力；注册表同时保留触发型/替代型横置能力的时机、来源和事件组元数据。多个 Ready Heimer 或原生/复制来源同时触发时，控制者可用 `order_optional` 排序。非横置能力（Vi、Udyr、Nocturne、Zhonya）不会进入复制候选。Nocturne 从牌库顶触发的替代窗口已覆盖 Vision、批量 reveal 和 Dazzling Aurora 的公共查看流程；Aurora 逐张公开到单位并通过普通免费出牌和 Chain continuation 继续。免费打出的目标法术与已覆盖的单位入场目标使用点击窗口。单位/装备/法术保留 `card_owner` 与控制者，跨控制回手、死亡、牺牲和清除按物理牌主处理。Volibear 已用五次可重复点击完成 5 点分配。代码不根据自然语言猜测效果，也不静默跳过未知关键词。

当前仍需单独完成的高优先规则项：少数 AbilityRegistry 的替代、递归复制和复杂事件能力尚未完整裁判化；部分跨区域控制权、复杂嵌套免费打出和战场可选效果仍缺少完整差分测试。普通施放与免费施放已经共用法术目标规格和资源窗口；目标确认后没有合法 Power/Deflect 支付时会安全退出并恢复父流程，牌保留在当前物理区域。`status` 中的 `full_origins_supported=false` 仍然有效：298 张代表目录、构筑和显式处理器覆盖，不代表每张牌都已完成官方裁判级验证。

测试通过只证明已执行的场景及不变量，没有官方裁判或另一套独立引擎的差分认证。当前训练文件用于有限卡池实验，不代表完整 Riftbound。引擎另外保留不进入普通观察和 GUI 的 `internal_event_log`，用于记录复杂结算的私有前后状态并验证回放。Greedy 与 Random 只是基准策略，不代表竞技水平。

回放规则 ID 绑定引擎语义版本、数据和双方套牌；改变处理器语义应升级版本。CLI 还检查 Python 主/次版本，回放逐步验证状态与随机数哈希。局面克隆和种子仅供特权训练/搜索代码使用，不应泄漏给只允许玩家观测的策略。
