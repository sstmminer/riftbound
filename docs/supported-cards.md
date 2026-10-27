# 可执行卡牌范围（0.3.0）

目录包含 Origins 298 个基础编号；以下 39 张才具有显式实现，并随包附带对应的清晰卡图与横置方向资源。未注册卡牌在套牌装载时拒绝。此版本不支持其余卡池、完整 Origins、Best-of-3 Match 或多人模式。

| 编号 | 名称 | 类型 | 已实现文本 |
| --- | --- | --- | --- |
| OGN-001 | Blazing Scorcher | unit | [Accelerate] (You may pay :rb_energy_1::rb_rune_fury: as an additional cost to have me enter ready.) |
| OGN-003 | Chemtech Enforcer | unit | [Assault 2]; when played, discard 1. |
| OGN-004 | Cleave | spell | [Action] (Play on your turn or in showdowns.) Give a unit [Assault 3] this turn. (+3 :rb_might: while it's an attacker.) |
| OGN-007 | Fury Rune | rune |  |
| OGN-009 | Hextech Ray | spell | [Action] (Play on your turn or in showdowns.) Deal 3 to a unit at a battlefield. |
| OGN-010 | Legion Rearguard | unit | [Accelerate] (You may pay :rb_energy_1::rb_rune_fury: as an additional cost to have me enter ready.) |
| OGN-011 | Magma Wurm | unit | Other friendly units enter ready. |
| OGN-012 | Noxus Hopeful | unit | [Legion] — I cost :rb_energy_2: less. (Get the effect if you've played another card this turn.) |
| OGN-013 | Pouty Poro | unit | [Deflect] (Opponents must pay :rb_rune_rainbow: to choose me with a spell or ability.) |
| OGN-015 | Captain Farron | unit | Other friendly units here have [Assault]. (+1 :rb_might: while they're attackers.) |
| OGN-024 | Void Seeker | spell | [Action] (Play on your turn or in showdowns.) Deal 4 to a unit at a battlefield. Draw 1. |
| OGN-027 | Darius, Trifarian | unit | When you play your second card in a turn, give me +2 :rb_might: this turn and ready me. |
| OGN-030 | Jinx, Demolitionist | unit | [Accelerate]; [Assault 2]; when played, discard 2. |
| OGN-039 | Kai'Sa, Survivor | unit | [Accelerate]; when I conquer, draw 1. |
| OGN-042 | Calm Rune | rune |  |
| OGN-088 | Mega-Mech | unit |  |
| OGN-166 | Chaos Rune | rune |  |
| OGN-089 | Mind Rune | rune |  |
| OGN-126 | Body Rune | rune |  |
| OGN-171 | Mystic Poro | unit | [Vision] — look at the top card of your Main Deck; you may recycle it. |
| OGN-175 | Shipyard Skulker | unit |  |
| OGN-176 | Sneaky Deckhand | unit | May be played to an open battlefield. |
| OGN-206 | Back to Back | spell | [Reaction] (Play any time, even before spells and abilities resolve.) Give two friendly units each +2 :rb_might: this turn. |
| OGN-207 | Call to Glory | spell | [Reaction] (Play any time, even before spells and abilities resolve.) As you play this, you may spend a buff as an additional cost. If you do, ignore this spell's cost. Give a unit +3 :rb_might: this turn. |
| OGN-210 | Daring Poro | unit | [Assault] (+1 :rb_might: while I'm an attacker.) |
| OGN-214 | Order Rune | rune |  |
| OGN-215 | Petty Officer | unit | [Assault] (+1 :rb_might: while I'm an attacker.) |
| OGN-217 | Trifarian Gloryseeker | unit | [Legion] — When you play me, buff me. (If I don't have a buff, I get a +1 :rb_might: buff. Get the effect if you've played another card this turn.) |
| OGN-219 | Vanguard Sergeant | unit |  |
| OGN-222 | Noxian Drummer | unit | When I move to a battlefield, play a 1 :rb_might: Recruit unit token here. (It is also at the battlefield.) |
| OGN-223 | Peak Guardian | unit | When you play me, buff me. Then, if I am at a battlefield, buff all other friendly units there. (To buff a unit, give it a +1 :rb_might: buff if it doesn't already have one.) |
| OGN-232 | Fiora, Victorious | unit | While I'm [Mighty], I have [Deflect], [Ganking], and [Shield]. (I'm Mighty while I have 5+ :rb_might:.) |
| OGN-251 | Loose Cannon | legend | At the start of your Beginning Phase, draw 1 if you have one or fewer cards in hand. |
| OGN-247 | Daughter of the Void | legend | Exhaust: add rainbow power usable only for spells. |
| OGN-253 | Hand of Noxus | legend | :rb_exhaust:: [Reaction], [Legion] — [Add] :rb_energy_1:. (Abilities that add resources can't be reacted to. Get the effect if you've played a card this turn.) |
| OGN-273 | Recruit (ZN) | unit |  |
| OGN-276 | Aspirant's Climb | battlefield | Increase the points needed to win the game by 1. |
| OGN-294 | Trifarian War Camp | battlefield | Units here have +1 :rb_might:. (This includes attackers.) |
| OGN-297 | Windswept Hillock | battlefield | Units here have [Ganking]. (They can move from battlefield to battlefield.) |

支持的规则仅就这套封闭卡池验证。Recruit 是衍生物，不可放入构筑主牌库。隐蔽、装备、死亡触发、卡牌反制、控制权改变等机制尚未开放；它们对应卡牌会被拒绝，不会当作白板处理。

扩展卡牌：OGN-039 Kai'Sa, Survivor 支持 Accelerate（额外支付 1 energy 与 fury power 后准备进入），并在征服时每张触发抽 1。可用符文目录现覆盖六个基础 domain（Fury、Calm、Mind、Body、Chaos、Order）；符文资源验证和回收会保留这些 domain。
