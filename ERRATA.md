# Riftbound 官方勘误整理

来自五篇官方公告，共 67 个公告内逐卡修订条目；其中 66 项已关联到 87 条印刷记录，剩余 1 项未匹配到图鉴卡牌。原始导出总计 93 行，其中 5 行是公告级原文记录，不能算作逐卡勘误。

**这是已有采集快照的整理，未重新访问官网。** 公告源响应的访问时间见 data/sources.json；图鉴文本、公告旧文本与修订文本分别保留。

所有引用为官方原文。名称匹配基于源完整名称；没有对 LeBlanc 的其他名称强行建立关联。

## 下载与数据文件

- [独立勘误 ZIP](downloads/riftbound-errata.zip)（含 JSON/CSV、完整公告文本、官方 HTML 快照与失败报告）。
- [errata.json](data/errata.json)
- [errata.csv](data/errata.csv)
- SQLite 的 errata 表也已包含这些内容：[完整数据库](data/riftbound.sqlite)。
- [采集失败与范围说明](FETCH-FAILURES.md)

## Ava Achiever

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-107-298`

### 公告旧文本

When I attack, you may pay [C] to play a card with [Hidden] from your hand here, ignoring its cost.

### 公告修订文本

When I attack, you may pay [C] to play a card with [Hidden] from your hand, ignoring its cost. If it’s a unit, play it here.

## Baited Hook

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-242-298`

### 公告旧文本

[1][C], [E]: Kill a friendly unit. Look at the top 5 cards of your Main Deck. You may play a unit from among them that has Might up to 1 more than the killed unit, ignoring its cost. Then recycle the rest.

### 公告修订文本

[1][C], [E]: Kill a friendly unit. Look at the top 5 cards of your Main Deck. You may banish a unit from among them that has Might up to 1 more than the killed unit and play it, ignoring its cost. Then recycle the rest.

## Blind Fury

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-025-298`

### 公告旧文本

[Action] (Play on your turn or in showdowns.)

Each opponent reveals the top card of their Main Deck. Choose one and play it, ignoring its cost. Then recycle the rest.

### 公告修订文本

[Action] (Play on your turn or in showdowns.)

Each opponent reveals the top card of their Main Deck. Choose one and banish it, then play it, ignoring its cost. Then recycle the rest.

## Clockwork Keeper

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-044-298`

### 公告旧文本

As you play me, you may pay [C] as an additional cost. If you do, draw 1.

### 公告修订文本

You may pay [C] as an additional cost to play me.

When you play me, if you paid the additional cost, draw 1.

## Convergent Mutation

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-108-298`

### 公告旧文本

[Reaction] (Play any time, even before spells and abilities resolve.)

Choose a friendly unit. Increase its Might until it equals the Might of another friendly unit.

### 公告修订文本

[Reaction] (Play any time, even before spells and abilities resolve.)

Choose a friendly unit. This turn, increase its Might to the Might of another friendly unit.

## Dark Child, Starter

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogs-017-024`

### 公告旧文本

At the end of your turn, ready 2 runes.

### 公告修订文本

At the end of your turn, ready up to 2 runes.

## Dazzling Aurora

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-160-298`

### 公告旧文本

At the end of your turn, reveal cards from the top of your Main Deck until you reveal a unit. Play it, ignoring its cost, and recycle the rest.

### 公告修订文本

At the end of your turn, reveal cards from the top of your Main Deck until you reveal a unit and banish it. Play it, ignoring its cost, and recycle the rest.

## Disintegrate

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-005-298`

### 公告旧文本

[Action] (Play on your turn or in showdowns.)

Deal 3 to a unit at a battlefield. If this kills it, draw 1.

### 公告修订文本

Action (Play on your turn or in showdowns.)

Deal 3 to a unit at a battlefield. If this kills it, do this: draw 1.

## Dragon's Rage

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-258-298`

### 公告旧文本

Move an enemy unit. Then choose another enemy unit at its destination. They deal damage equal to their Mights to each other.

### 公告修订文本

Move an enemy unit. Then do this: Choose another enemy unit at its destination. They deal damage equal to their Mights to each other.

## Dune Drake

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-131-298`

### 公告旧文本

When I attack, give me +2 [M] if there is a ready enemy unit here.

### 公告修订文本

When I attack, give me +2 [M] this turn if there is a ready enemy unit here.

## Highlander

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogs-020-024`

### 公告旧文本

[Reaction] (Play any time, even before spells and abilities resolve.)

Choose a friendly unit. The next time it dies this turn, recall it exhausted instead. (Send it to base. This isn't a move.)

### 公告修订文本

[Reaction] (Play any time, even before spells and abilities resolve.)

Choose a friendly unit. The next time it would die this turn, heal it, exhaust it, and recall it instead. (Send it to base. This isn't a move.)

## Karma, Channeler

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-235-298`, `sfd-237-221`, `sfd-237-star-221`

### 公告旧文本

[Vision] (When you play me, look at the top card of your Main Deck. You may recycle it.)

When you recycle one or more cards, buff a friendly unit. (If it doesn't have a buff, it gets a +1 [M] buff. Runes aren't cards.)

### 公告修订文本

[Vision] (When you play me, look at the top card of your Main Deck. You may recycle it.)

When you recycle one or more cards to your Main Deck, buff a friendly unit. (If it doesn't have a buff, it gets a +1 [M] buff. Runes aren't cards.)

## Kinkou Monk

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-141-298`

### 公告旧文本

When you play me, buff two other friendly units. (Each one that doesn't have a buff gets a +1 [M] buff.)

### 公告修订文本

When you play me, buff up to two other friendly units. (Each one that doesn't have a buff gets a +1 [M] buff.)

## Nocturne, Horrifying

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-194-298`

### 公告旧文本

[Ganking] (I can move from battlefield to battlefield.)

When you look at cards from the top of your deck (and don't draw them) and see me, you may play me for [A].

### 公告修订文本

[Ganking] (I can move from battlefield to battlefield.)

As you look at or reveal me from the top of your deck, you may banish me. If you do, you may play me for [A].

## Pack of Wonders

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-181-298`

### 公告旧文本

[E]: Return another friendly gear, unit, or [Hidden] card to its owner's hand.

### 公告修订文本

[E]: Return another friendly gear, unit, or facedown card to its owner's hand.

## Portal Rescue

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-102-298`

### 公告旧文本

[Action] (Play on your turn or in showdowns.)

Banish a friendly unit, then play it to base, ignoring its cost.

Note: Text only differs for English version of the card

### 公告修订文本

[Action] (Play on your turn or in showdowns.)

Banish a friendly unit, then its owner plays it to their base, ignoring its cost.

## Promising Future

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-115-298`

### 公告旧文本

Each player looks at the top 5 cards of their Main Deck, chooses one, then recycles the rest. Starting with the next player, each player plays those cards, ignoring Energy costs. (They must still pay Power costs.)

### 公告修订文本

Each player looks at the top 5 cards of their Main Deck, banishes one of them, then recycles the rest. Starting with the next player, each player plays those cards, ignoring Energy costs. (They must still pay Power costs.)

## Ravenborn Tome

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-032-298`

### 公告旧文本

[E]: The next spell you play deals 1 Bonus Damage. (Each instance of damage the spell deals is increased by 1.)

### 公告修订文本

[E]: The next spell you play this turn deals 1 Bonus Damage. (Each instance of damage the spell deals is increased by 1.)

## Salvage

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-224-298`

### 公告旧文本

[Action] (Play on your turn or in showdowns.)

You may kill a gear. Draw 1.

### 公告修订文本

[Action] (Play on your turn or in showdowns.)

You may kill up to one gear. Draw 1.

## Sigil of the Storm

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-287-298`

### 公告旧文本

When you conquer here, recycle one of your runes.

### 公告修订文本

When you conquer here, you must recycle one of your runes. (This doesn’t choose anything.)

## Sona, Harmonious

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-073-298`, `ven-sp2-006`

### 公告旧文本

While I'm at a battlefield, ready 4 friendly runes at the end of your turn.

### 公告修订文本

At the end of your turn, if I'm at a battlefield, ready up to 4 friendly runes.

## Targon's Peak

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-289-298`

### 公告旧文本

When you conquer here, ready 2 runes at the end of this turn.

### 公告修订文本

When you conquer here, ready up to 2 runes at the end of this turn.

## Teemo, Strategist

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-121-298`, `ogn-121a-298`, `sfd-230-221`, `sfd-230-star-221`

### 公告旧文本

[Hidden] (Hide now for [A] to react with later for [0].)

When I defend or I'm played from [Hidden], reveal the top 5 cards of your Main Deck. Deal 1 to an enemy unit here for each card with [Hidden], then recycle them.

### 公告修订文本

[Hidden] (Hide now for [A] to react with later for [0].)

When I defend, choose an enemy unit here and reveal the top 5 cards of your Main Deck. Deal 1 to that unit for each card with [Hidden] revealed this way, then recycle the revealed cards.

## The Boss

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-269-298`, `ogn-310-298`, `ogn-310-star-298`

### 公告旧文本

When a buffed unit you control would die, you may pay [C] and exhaust me to spend its buff and recall it exhausted instead. (Send it to base. This isn't a move.)

When you conquer, ready me.

### 公告修订文本

If a buffed unit you control would die, you may pay [C], exhaust me, and spend its buff to heal it, exhaust it, and recall it instead. (Send it to base. This isn't a move.)

When you conquer, ready me.

## The Dreaming Tree

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-292-298`

### 公告旧文本

The first time you choose a friendly unit with a spell here each turn, draw 1.

### 公告修订文本

When a player chooses a friendly unit here with a spell for the first time each turn, they draw 1.

## The Syren

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-184-298`

### 公告旧文本

[1], [E]: Move a friendly unit at a battlefield to your base.

Note: Text only differs for English version of the card

### 公告修订文本

[1], [E]: Move a friendly unit at a battlefield to its base.

## Tideturner

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-199-298`

### 公告旧文本

[Hidden] (Hide now for [A] to react with later for [0].)

When you play me, you may choose a friendly unit. Move me to its location and it to my original location.

### 公告修订文本

[Hidden] (Hide now for [A] to react with later for [0].)

When you play me, you may choose a unit you control at another location. Move me to its location and it to my original location.

## Unforgiven

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-259-298`, `ogn-305-298`, `ogn-305-star-298`

### 公告旧文本

[2], [E]: Move a friendly unit to or from your base.

Note: Text only differs for English version of the card

### 公告修订文本

[2], [E]: Move a friendly unit to or from its base.

## Unlicensed Armory

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-023-298`

### 公告旧文本

Discard 1, [E]: Choose a friendly unit. The next time it dies this turn, you may pay [C] to recall it exhausted instead. (Send it to base. This isn't a move.)

### 公告修订文本

Discard 1, [E]: Choose a friendly unit. The next time it would die this turn, you may pay [C] to heal it, exhaust it, and recall it instead. (Send it to base. This isn't a move.)

## Void Gate

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-296-298`

### 公告旧文本

Spells and abilities affecting units here each deal 1 Bonus Damage. (Each instance of damage the spell deals is increased by 1.)

### 公告修订文本

Spells and abilities deal 1 Bonus Damage to units here. (Each instance of damage the spell deals to a unit here is increased by 1.)

## Zhonya's Hourglass

- 系列：Origins
- 公告日期：2025-10-28T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-origins-card-errata/
- 关联印刷 ID：`ogn-077-298`

### 公告旧文本

[Hidden] (Hide now for [A] to react with later for [0].)

The next time a friendly unit would die, kill this instead. Recall that unit exhausted. (Send it to base. This isn't a move.)

### 公告修订文本

[Hidden] (Hide now for [A] to react with later for [0].)

If a friendly unit would die, kill this instead. Heal that unit, exhaust it, and recall it. (Send it to base. This isn't a move.)

## Arise!

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-198-221`

### 公告旧文本

Play a 2 [M] Sand Soldier unit token for each Equipment you control. Then ready two of them.

### 公告修订文本

Play a 2 [M] Sand Soldier unit token for each Equipment you control. Then do this: Ready up to two of them.

## Blood Rush

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-003-221`

### 公告旧文本

[Action] (Play on your turn or in showdowns.)

[Repeat] [1] (You may pay the additional cost to repeat this spell's effect.)

Give a unit [Assault 2]. (+2 [M] while it's an attacker.)

### 公告修订文本

[Action] (Play on your turn or in showdowns.)

[Repeat] [1] (You may pay the additional cost to repeat this spell's effect.)

Give a unit [Assault 2] this turn. (+2 [M] while it's an attacker.)

## Deathgrip

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-163-221`

### 公告旧文本

[Reaction] (Play any time, even before spells and abilities resolve.)

Kill a friendly unit to give +[M] equal to its Might to another friendly unit this turn. Draw 1.

### 公告修订文本

[Reaction] (Play any time, even before spells and abilities resolve.)

Kill a friendly unit. If you do, give +[M] equal to its Might to another friendly unit this turn.

Draw 1.

## Edge of Night

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-139-221`

### 公告旧文本

[Hidden] (Hide now for [A] to react with later for [0].)

When you play this from face down, attach it to a unit you control here.

[Equip] [C] ([C]: Attach this to a unit you control.)

### 公告修订文本

[Hidden] (Hide now for [A] to react with later for [0].)

When you play this from face down, attach it to a unit you control (here).

[Equip] [C] ([C]: Attach this to a unit you control.)

## Falling Star

- 系列：Origins
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`ogn-029-298`

### 公告旧文本

Do this twice:

Deal 3 to a unit. (You can choose different units.)

### 公告修订文本

Deal 3 to a unit.

Deal 3 to a unit.

## Icathian Rain

- 系列：Origins
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`ogn-248-298`

### 公告旧文本

Do this 6 times:

Deal 2 to a unit. (You can choose different units.)

### 公告修订文本

Deal 2 to a unit.

Deal 2 to a unit.

Deal 2 to a unit.

Deal 2 to a unit.

Deal 2 to a unit.

Deal 2 to a unit.

## Janna, Savior

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-053-221`

### 公告旧文本

[Reaction] (Play any time, even before spells and abilities resolve, including to a battlefield you control.)

When you play me, heal your units here, then move an enemy unit from here to its base.

### 公告修订文本

[Reaction] (Play any time, even before spells and abilities resolve, including to a battlefield you control.)

When you play me, heal your units here, then move up to one enemy unit from here to its base.

## Jax, Unmatched

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-054-221`, `sfd-054a-221`

### 公告旧文本

[Deflect] (Opponents must pay [A] to choose me with a spell or ability.)

Each Equipment in your hand has [Quick-Draw]. (It gains [Reaction]. When you play it, attach it to a unit you control.)

### 公告修订文本

[Deflect] (Opponents must pay [A] to choose me with a spell or ability.)

Your Equipment everywhere have [Quick-Draw]. (Each gains [Reaction]. When you play it, attach it to a unit you control.)

## Kato the Arm

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-112-221`

### 公告旧文本

[Deflect] (Opponents must pay [A] to choose me with a spell or ability.)

When I move to a battlefield, give a friendly unit my keywords and +[M] equal to my Might this turn.

### 公告修订文本

[Deflect] (Opponents must pay [A] to choose me with a spell or ability.)

When I move to a battlefield, give another friendly unit my keywords and +[M] equal to my Might this turn.

## Reinforce

- 系列：Origins
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`ogn-062-298`

### 公告旧文本

Look at the top 5 cards of your Main Deck. You may play a unit from among them. Its Energy cost is reduced by [5]. Then recycle the remaining cards.

### 公告修订文本

Look at the top 5 cards of your Main Deck. You may banish a unit from among them, then play it, reducing its cost by [5]. Recycle the remaining cards.

## Rek’Sai, Swarm Queen

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-170-221`, `sfd-170a-221`

### 公告旧文本

When I attack, you may reveal the top 2 cards of your Main Deck. You may play one. Then recycle the rest. If the played card is a unit, you may play it here.

### 公告修订文本

When I attack, you may reveal the top 2 cards of your Main Deck. You may banish one, then play it. If it is a unit, you may play it here. Recycle the rest.

## Rell, Magnetic

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-024-221`

### 公告旧文本

[Tank] (I must be assigned combat damage first.)

When I attack, you may play an Equipment with Energy cost no more than [2], ignoring its cost, and attach it to me.

### 公告修订文本

[Tank] (I must be assigned combat damage first.)

When I attack, you may play an Equipment with Energy cost no more than [2], ignoring its cost. If you do, then do this: Attach it to me.

## Tianna Crownguard

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-060-221`

### 公告旧文本

[Deflect] (Opponents must pay [A] to choose me with a spell or ability.)

While I'm at a battlefield, opponents can't score points.

### 公告修订文本

[Deflect] (Opponents must pay [A] to choose me with a spell or ability.)

While I'm at a battlefield, opponents can't gain points.

## Void Burrower

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-187-221`, `sfd-243-221`

### 公告旧文本

When you conquer, you may exhaust me to reveal the top 2 cards of your Main Deck. You may play one. Then recycle the rest.

### 公告修订文本

When you conquer, you may exhaust me to reveal the top 2 cards of your Main Deck. You may banish one, then play it. Recycle the rest.

## Void Rush

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`sfd-188-221`

### 公告旧文本

Reveal the top 2 cards of your Main Deck. You may play one of them, reducing its cost by [2]. Draw any you did not play this way.

### 公告修订文本

Reveal the top 2 cards of your Main Deck. You may banish one, then play it, reducing its cost by [2]. Draw any you didn't banish.

## Yone, Blademaster

- 系列：Spiritforged
- 公告日期：2026-01-14T02:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/riftbound-spiritforged-errata/
- 关联印刷 ID：`rad-181-167`, `sfd-116-221`, `sfd-233-221`, `sfd-233-star-221`

### 公告旧文本

[Weaponmaster] (When you play me, you may [Equip] one of your Equipment to me for [A] less, even if it's already attached.)

When I conquer an open battlefield, deal damage equal to my Might to an enemy unit in a base.

### 公告修订文本

[Weaponmaster] (When you play me, you may [Equip] one of your Equipment to me for [A] less, even if it's already attached.)

When I conquer a battlefield that was uncontrolled, deal damage equal to my Might to an enemy unit in a base.

## Bone Skewer

- 系列：Unleashed
- 公告日期：2026-04-03T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/
- 关联印刷 ID：`unl-139-219`

### 公告旧文本

[Hidden] (Hide now for [A] to react with later for [0].)

Choose a battlefield. An opponent reveals their hand. You may choose a unit from it. They play that unit to that battlefield, ignoring any and all costs. When they do, [Stun] it. (It doesn't deal combat damage this turn.)

### 公告修订文本

[Hidden] (Hide now for [A] to react with later for [0].)

Choose a battlefield. An opponent reveals their hand. You may choose a unit from it. They play that unit to that battlefield, ignoring any and all costs. If they do, then do this: [Stun] it. (It doesn't deal combat damage this turn.)

## Death from Below

- 系列：Unleashed
- 公告日期：2026-04-03T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/
- 关联印刷 ID：`unl-186-219`

### 公告旧文本

Kill a unit at a battlefield. Then, if it had 3 [M] or less, you may play this from your trash for [A].

### 公告修订文本

Kill a unit at a battlefield. Then, if it had 3 [M] or less, do this: You may play this from your trash for [A].

## Guards!

- 系列：Spiritforged
- 公告日期：2026-04-03T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/
- 关联印刷 ID：`sfd-154-221`

### 公告旧文本

[Hidden] (Hide now for [A] to react with later for [0].)

Play a 2 [M] Sand Soldier unit token. You may pay [C] to ready it.

### 公告修订文本

[Hidden] (Hide now for [A] to react with later for [0].)

Play a 2 [M] Sand Soldier unit token. Then do this: You may pay [C] to ready it.

## Keeper of Masks

- 系列：Unleashed
- 公告日期：2026-04-03T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/
- 关联印刷 ID：`unl-081-219`

### 公告旧文本

[Hidden] (Hide now for [A] to react with later for [0].)

[Temporary] (Kill me at the start of my controller's Beginning Phase, before scoring.)

When you play me, play two Reflection unit tokens here. They become copies of me.

### 公告修订文本

[Hidden] (Hide now for [A] to react with later for [0].)

[Temporary] (Kill me at the start of my controller's Beginning Phase, before scoring.)

When you play me, play two Reflection unit tokens here. Then do this: They become copies of me.

## Leblanc, Deceiver

- 系列：Unleashed
- 公告日期：2026-04-03T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/
- 关联印刷 ID：**未匹配；不猜测关联**

### 公告旧文本

When you conquer or hold, you may discard 1 and exhaust me to play a ready Reflection unit token there. It becomes a copy of another unit there. Give it [Temporary].

### 公告修订文本

When you conquer or hold, you may discard 1 and exhaust me to play a ready Reflection unit token there. Then do this: It becomes a copy of another unit there. Give it [Temporary].

## Mirror Image

- 系列：Unleashed
- 公告日期：2026-04-03T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/
- 关联印刷 ID：`unl-200-219`

### 公告旧文本

Choose a unit. Play a ready Reflection unit token to your base. It becomes a copy of that unit. Give it [Temporary]. (Kill it at the start of its controller's Beginning Phase, before scoring.)

### 公告修订文本

Choose a unit. Play a ready Reflection unit token to your base. Then do this: It becomes a copy of that unit. Give it [Temporary]. (Kill it at the start of its controller's Beginning Phase, before scoring.)

## Relentless Pursuit

- 系列：Spiritforged
- 公告日期：2026-04-03T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/
- 关联印刷 ID：`sfd-184-221`

### 公告旧文本

[Action] (Play on your turn or in showdowns.)

Move a friendly unit. You may attach an Equipment with the same controller to it. This turn, that unit has "When I conquer, you may move me to my base."

### 公告修订文本

[Action] (Play on your turn or in showdowns.)

Move a friendly unit. You may attach up to one Equipment with the same controller to it. This turn, that unit has "When I conquer, you may move me to my base."

## Rengar, Trophy Hunter

- 系列：Unleashed
- 公告日期：2026-04-03T01:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/rules-and-releases/unleashed-errata-updates/
- 关联印刷 ID：`unl-120-219`, `unl-120a-219`, `ven-179-166`

### 公告旧文本

[Ambush] (You may play me as a [Reaction] to a battlefield where you have units.)

I can be played to a battlefield where there are enemy units (even if you don't have units there).

### 公告修订文本

[Ambush] (You may play me as a [Reaction] to a battlefield where you have units.)

I can [Ambush] to a battlefield where there are enemy units, even if you don't have units there.

## Astral Heron

- 系列：Vendetta
- 公告日期：2026-07-23T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/vendetta-errata-updates/
- 关联印刷 ID：`ven-044-166`

### 公告旧文本

When you play your first card each turn, if I'm at a battlefield, your next card costs [2][A][A] less.

### 公告修订文本

When you play your first card each turn, if I'm at a battlefield, the next card you play this turn costs [2][A][A] less.

## Diana, Lunari

- 系列：Unleashed
- 公告日期：2026-07-23T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/vendetta-errata-updates/
- 关联印刷 ID：`unl-079-219`, `unl-079a-219`

### 公告旧文本

When a showdown begins here, you may pay [1]. If you do, [Predict], then reveal the top card of your Main Deck. If it's a spell, draw it. (To Predict, look at the top card of your Main Deck. You may recycle it.)

### 公告修订文本

When a showdown begins here, you may pay [1] to [Predict], then reveal the top card of your Main Deck. If it's a spell, draw it. (To Predict, look at the top card of your Main Deck. You may recycle it.)

## Draven, Vanquisher

- 系列：Spiritforged
- 公告日期：2026-07-23T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/vendetta-errata-updates/
- 关联印刷 ID：`sfd-020-221`, `sfd-020a-221`

### 公告旧文本

When I win a combat, play a Gold gear token exhausted.

When I attack or defend, you may pay [C]. If you do, give me +2 [M] this turn.

### 公告修订文本

When I win a combat, play a Gold gear token exhausted.

When I attack or defend, you may pay [C] to give me +2 [M] this turn.

## Emperor’s Dais

- 系列：Spiritforged
- 公告日期：2026-07-23T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/vendetta-errata-updates/
- 关联印刷 ID：`sfd-207-221`

### 公告旧文本

When you conquer here, you may pay [1] and return a unit you control here to its owner's hand. If you do, play a 2 [M] Sand Soldier unit token here.

### 公告修订文本

When you conquer here, you may pay [1] and return a unit you control here to its owner's hand to play a 2 [M] Sand Soldier unit token here.

## Fizz, Trickster

- 系列：Spiritforged
- 公告日期：2026-07-23T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/vendetta-errata-updates/
- 关联印刷 ID：`sfd-140-221`

### 公告旧文本

When you play me, you may play a spell from your trash with Energy cost no more than [3], ignoring its Energy cost. Recycle that spell after you play it. (You must still pay its Power cost.)

### 公告修订文本

When you play me, you may play a spell from your trash with Energy cost no more than [3], ignoring its Energy cost. Then recycle it. (You must still pay its Power cost.)

## Gangplank, Naval

- 系列：Vendetta
- 公告日期：2026-07-23T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/vendetta-errata-updates/
- 关联印刷 ID：`ven-086-166`, `ven-181-166`

### 公告旧文本

[Empower] [C][C] ([C][C]: Empower me. Use only if not Empowered.)

[Empowered][>] If a spell or ability that chooses me would stun me, give me -[M], or return me to hand, give me +3 [M] instead.

### 公告修订文本

[Empower] [C][C] ([C][C]: Empower me. Use only if not Empowered.)

[Empowered][>] If a spell or ability that chooses me would stun me, give me -[M], or return me to hand, give me +3 [M] this turn instead.

## Resonating Strike

- 系列：Vendetta
- 公告日期：2026-07-23T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/vendetta-errata-updates/
- 关联印刷 ID：`ven-034-166`

### 公告旧文本

[Hidden] (Hide now for [A] to react with later for [0].)

[Reaction] (Play on your turn or in showdowns.)

Choose a battlefield you control and a unit you control at a different location. Move that unit to that battlefield and give it +2 [S] this turn.

### 公告修订文本

[Hidden] (Hide now for [A] to react with later for [0].)

[Reaction] (Play any time, even before spells and abilities resolve.)

Choose a battlefield you control and a unit you control at a different location. Move that unit to that battlefield and give it +2 [S] this turn.

## Stalking Wolf

- 系列：Unleashed
- 公告日期：2026-07-23T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/vendetta-errata-updates/
- 关联印刷 ID：`unl-166-219`

### 公告旧文本

[Ambush] (You may play me as a [Reaction] to a battlefield where you have units.)

As an additional cost to play me, kill a Bird, Cat, Dog, or Poro you control. You may play me to its battlefield (even if you don't have other units there).

### 公告修订文本

[Ambush] (You may play me as a [Reaction] to a battlefield where you have units.)

As an additional cost to play me, kill a Bird, Cat, Dog, or Poro you control. You may [Ambush] me to its battlefield, even if you don't have other units there.

## Elnuk Herd

- 系列：Radiance
- 公告日期：2026-10-09T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/radiance-errata-updates/
- 关联印刷 ID：`rad-081-167`

### 公告旧文本

[Hidden] (Hide now for [A] to react with later for [0].)

When you play me, give another friendly unit +3 [M] this turn, then recycle me if I was played from face down.

### 公告修订文本

[Hidden] (Hide now for [A] to react with later for [0].)

When you play me, give a friendly unit +3 [M] this turn, then recycle me if I was played from face down.

## Forbidden Technique

- 系列：Radiance
- 公告日期：2026-10-09T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/radiance-errata-updates/
- 关联印刷 ID：`rad-010-167`

### 公告旧文本

Ready a unit.

When you play a card with Energy cost [7] or more, you may play this from your trash for [1][C][C]. Banish this.

### 公告修订文本

Ready a unit.

When you play a card with Energy cost [7] or more, you may play this from your trash for [1][C][C]. Then banish this.

## Last Caress

- 系列：Radiance
- 公告日期：2026-10-09T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/radiance-errata-updates/
- 关联印刷 ID：`rad-154-167`

### 公告旧文本

[Reaction] (Play any time, even before spells and abilities resolve.)

The next unit you play this turn (even from face down) can be played to any battlefield. When you play it, [Buff] it. (Give it a +1 [M] buff if it doesn't have one.)

### 公告修订文本

[Reaction] (Play any time, even before spells and abilities resolve.)

The next unit you play this turn, even from face down, can be played to any battlefield. When you play it, [Buff] it. (Give it a +1 [M] buff if it doesn't have one.)

## Neeko, Blending In

- 系列：Radiance
- 公告日期：2026-10-09T16:00:00.000Z
- 官方来源：https://playriftbound.com/en-us/news/announcements/radiance-errata-updates/
- 关联印刷 ID：`rad-167-167`

### 公告旧文本

(Neutral cards can go in decks of any Domain.)

If Neeko is in your deck, choose 3 different legends in addition to your starting legend. (Different means none match names.)

When you play me, choose one of those Legends and add it to your Legend Zone while I'm on the board.

### 公告修订文本

(Neutral cards can go in decks of any Domain.)

If Neeko is in your deck, choose up to 3 different legends in addition to your starting legend. (Different means none match names.)

When you play me, choose one of those Legends and add it to your Legend Zone while I'm on the board.
