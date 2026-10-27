"""Audited core operations for RUP5, updated 2026-10-09.

These are composable operations, NOT a complete Rules backend. Each function
states its prerequisites. Triggers, replacement effects, timing and cleanup
scheduling remain the responsibility of a future orchestrator.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from itertools import permutations
import random


DOMAINS = frozenset({"fury", "calm", "mind", "body", "chaos", "order"})


@dataclass(frozen=True)
class Card:
    id: str
    name: str
    kind: str
    domains: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    champion: bool = False
    signature: bool = False
    unique: bool = False
    rules_text: str = ""

    def __post_init__(self):
        if not self.id or not self.name:
            raise ValueError("cards need an ID and a name")
        if self.kind not in {"unit", "gear", "spell", "rune", "legend", "battlefield"}:
            raise ValueError("unknown card type")
        if not self.domains <= DOMAINS:
            raise ValueError("unknown domain")


@dataclass(frozen=True)
class Deck:
    legend: str
    chosen_champion: str
    main: tuple[str, ...]  # Includes the physical chosen champion (103.3).
    runes: tuple[str, ...]
    battlefields: tuple[str, ...]


def validate_deck(deck: Deck, cards: dict[str, Card]) -> None:
    """103 and 487: base Duel construction; not format legality or card overrides.

    Extra deck-construction permissions in card text are not evaluated here.
    Successful validation does not mean card effects are implemented.
    """
    all_ids = (deck.legend, deck.chosen_champion, *deck.main, *deck.runes, *deck.battlefields)
    missing = set(all_ids) - cards.keys()
    if missing:
        raise ValueError(f"unknown card IDs: {sorted(missing)}")
    legend, chosen = cards[deck.legend], cards[deck.chosen_champion]
    if legend.kind != "legend":
        raise ValueError("103.2: a champion legend is required")
    if chosen.kind != "unit" or not chosen.champion or chosen.signature or not (chosen.tags & legend.tags):
        raise ValueError("103.3.a.2: chosen champion must match legend champion tag")
    if len(deck.main) < 40 or deck.chosen_champion not in deck.main:
        raise ValueError("103.3: main deck needs at least 40 cards including chosen champion")
    if any(cards[c].kind not in {"unit", "gear", "spell"} for c in deck.main):
        raise ValueError("103.3: invalid main deck card type")
    counts = Counter(cards[c].name for c in deck.main)
    unique_names = {cards[c].name for c in deck.main if cards[c].unique}
    if any(n > (1 if name in unique_names else 3) for name, n in counts.items()):
        raise ValueError("103.3.b/825.3: same-name copy limit exceeded")
    signatures = [cards[c] for c in deck.main if cards[c].signature]
    if len(signatures) > 3 or any(not (c.tags & legend.tags) for c in signatures):
        raise ValueError("103.3.d: signature count or champion tag invalid")
    if len(deck.runes) != 12 or any(cards[c].kind != "rune" for c in deck.runes):
        raise ValueError("103.4: exactly 12 runes required")
    if len(deck.battlefields) != 3 or any(cards[c].kind != "battlefield" for c in deck.battlefields):
        raise ValueError("487.4: three battlefield choices required")
    if len({cards[c].name for c in deck.battlefields}) != 3:
        raise ValueError("103.5.c: battlefield names must differ")
    if any(not cards[c].domains <= legend.domains for c in (*deck.main, *deck.runes, *deck.battlefields)):
        raise ValueError("103.2.b: card lies outside domain identity")


def setup_duel(decks: tuple[Deck, Deck], cards: dict[str, Card], rng: random.Random) -> dict:
    """111–117, 487.5: pre-mulligan state; index 0 is top of each deck.

    No card text or additional setup choices are executed. Output is privileged.
    """
    if len(decks) != 2:
        raise ValueError("Duel needs two decks")
    for deck in decks:
        validate_deck(deck, cards)
    players = []
    for deck in decks:
        main, runes = list(deck.main), list(deck.runes)
        main.remove(deck.chosen_champion)
        rng.shuffle(main)
        rng.shuffle(runes)
        players.append({"legend": deck.legend, "champion_zone": [deck.chosen_champion],
                        "hand": main[:4], "main": main[4:], "rune_deck": runes,
                        "trash": [], "battlefield": rng.choice(deck.battlefields)})
    return {"first_player": rng.randrange(2), "players": players}


def mulligan(hand: list[str], main: list[str], slots: tuple[int, ...], rng: random.Random):
    """117: choose up to two; draw replacements BEFORE recycling set-aside cards.

    Only for normal setup (the 35-card remainder cannot burn out).
    Inputs remain unchanged; returned lists are new.
    """
    if len(slots) > 2 or len(set(slots)) != len(slots):
        raise ValueError("117.1: choose at most two distinct hand slots")
    if any(type(i) is not int or not 0 <= i < len(hand) for i in slots):
        raise ValueError("invalid mulligan slot")
    if len(main) < len(slots):
        raise ValueError("mulligan requires normal setup deck size")
    removed = [hand[i] for i in slots]
    rng.shuffle(removed)  # 417.5, randomized order at bottom, not a full shuffle.
    return ([card for i, card in enumerate(hand) if i not in slots] + main[:len(slots)],
            main[len(slots):] + removed)


@dataclass
class Rune:
    id: str
    domain: str
    exhausted: bool = False

    def __post_init__(self):
        if self.domain not in DOMAINS:
            raise ValueError("unknown rune domain")


@dataclass
class Pool:
    energy: int = 0
    power: list[str] = field(default_factory=list)  # "any" is universal power.

    def exhaust_basic(self, rune: Rune) -> None:
        """164.2.a; resource abilities resolve immediately under 337.2."""
        if rune.exhausted:
            raise ValueError("rune is already exhausted")
        rune.exhausted = True
        self.energy += 1

    def recycle_basic(self, rune_id: str, board: list[Rune], deck: list[Rune]) -> None:
        """164.2.b, 417: even an exhausted rune may recycle for power."""
        rune = next((r for r in board if r.id == rune_id), None)
        if rune is None:
            raise ValueError("rune is not controlled on board")
        board.remove(rune)
        self.power.append(rune.domain)
        deck.append(Rune(rune.id, rune.domain))  # New zone object (124).

    def pay(self, energy: int, requirements: tuple[frozenset[str], ...], slots: tuple[int, ...]) -> None:
        """445: explicit power allocation, preserving the player's payment choice.

        A requirement is the set of acceptable domains: {calm, chaos} for a
        dual-domain [C], DOMAINS for [A]. Universal power meets any requirement.
        Rune activation choices must happen before calling this primitive.
        """
        if type(energy) is not int or energy < 0:
            raise ValueError("energy cost must be a nonnegative integer")
        if len(requirements) != len(slots) or len(set(slots)) != len(slots):
            raise ValueError("invalid power payment allocation")
        if any(not r or not r <= DOMAINS for r in requirements):
            raise ValueError("invalid power cost")
        if self.energy < energy or any(type(i) is not int or not 0 <= i < len(self.power) for i in slots):
            raise ValueError("insufficient resources")
        if any(self.power[i] != "any" and self.power[i] not in req for req, i in zip(requirements, slots)):
            raise ValueError("power domain mismatch")
        self.energy -= energy
        self.power[:] = [power for i, power in enumerate(self.power) if i not in slots]

    def empty(self) -> None:
        """167: at every Main Phase start and every turn end, for both players."""
        self.energy = 0
        self.power.clear()


@dataclass
class Gear:
    """A face-up gear permanent in a player's equipment zone."""
    id: str
    controller: int
    exhausted: bool = False  # Gear enters ready/vertical unless its text says otherwise.
    resource_domain: str | None = None

    def __post_init__(self) -> None:
        if not self.id or self.controller not in (0, 1):
            raise ValueError("invalid gear")
        if self.resource_domain is not None and self.resource_domain not in DOMAINS:
            raise ValueError("unknown gear resource domain")


@dataclass
class GearZone:
    """Minimal equipment zone; card text is represented by explicit hooks."""
    cards: list[Gear] = field(default_factory=list)
    trash: list[str] = field(default_factory=list)

    def play(self, card: Card, *, controller: int, resource_domain: str | None = None) -> Gear:
        if card.kind != "gear":
            raise ValueError("only gear cards can enter the equipment zone")
        if controller not in (0, 1):
            raise ValueError("invalid gear controller")
        if any(g.id == card.id for g in self.cards):
            raise ValueError("gear ID is already in the equipment zone")
        gear = Gear(card.id, controller, False, resource_domain)
        self.cards.append(gear)
        return gear

    def kill(self, gear_id: str, *, controller: int | None = None) -> str:
        gear = next((g for g in self.cards if g.id == gear_id), None)
        if gear is None or (controller is not None and gear.controller != controller):
            raise ValueError("gear is not controlled in the equipment zone")
        self.cards.remove(gear)
        self.trash.append(gear.id)
        return gear.id

    def ready(self, gear_id: str, *, controller: int) -> None:
        gear = next((g for g in self.cards if g.id == gear_id), None)
        if gear is None or gear.controller != controller:
            raise ValueError("gear is not controlled in the equipment zone")
        gear.exhausted = False

    def activate_resource(self, gear_id: str, *, controller: int, pool: Pool) -> None:
        """Exhaust a supported resource gear to add one domain power."""
        gear = next((g for g in self.cards if g.id == gear_id), None)
        if gear is None or gear.controller != controller:
            raise ValueError("gear is not controlled in the equipment zone")
        if gear.resource_domain is None:
            raise ValueError("gear has no supported resource ability")
        if gear.exhausted:
            raise ValueError("gear is already exhausted")
        gear.exhausted = True
        pool.power.append(gear.resource_domain)


def channel_count(*, first_turn: bool, second_player: bool, available: int) -> int:
    """315.3 and 487.7: 2 normally, 3 on the second player's first turn."""
    if type(available) is not int or available < 0:
        raise ValueError("invalid available rune count")
    return min(2 + int(first_turn and second_player), available)


@dataclass(frozen=True)
class DrawResult:
    drawn: tuple[str, ...]
    main: tuple[str, ...]
    trash: tuple[str, ...]
    points: tuple[int, int]
    burnouts: int
    immediate_winner: int | None


def draw_cards(main: tuple[str, ...], trash: tuple[str, ...], count: int,
               *, player: int, points: tuple[int, int], rng: random.Random,
               victory: int = 8) -> DrawResult:
    """414, 432: draw without card replacement/prevention/trigger effects.

    In Duel the opponent choice is forced. Returning immediate_winner applies
    only to repeated burnouts (432.3.c), otherwise check victory at cleanup.
    Caller must add drawn cards to hand. Does not mutate input collections.
    """
    if type(count) is not int or count < 0 or player not in (0, 1):
        raise ValueError("invalid draw")
    if len(points) != 2 or any(type(p) is not int or p < 0 for p in points) or victory < 1:
        raise ValueError("invalid score")
    deck, discarded, score = list(main), list(trash), list(points)
    drawn, burns, winner = [], 0, None
    while len(drawn) < count:
        if deck:
            drawn.append(deck.pop(0))
            continue
        burns += 1
        deck, discarded = discarded, []
        rng.shuffle(deck)
        opponent = 1-player
        score[opponent] += 1
        if burns > 1 and score[opponent] >= victory and score[opponent] > score[player]:
            winner = opponent
            break
    return DrawResult(tuple(drawn), tuple(deck), tuple(discarded), tuple(score), burns, winner)


@dataclass(frozen=True)
class MovingUnit:
    id: str
    controller: int
    location: str  # base:0, base:1, battlefield:0, battlefield:1
    exhausted: bool = True  # 143.4: enter exhausted by default.


def standard_move(units: tuple[MovingUnit, ...], selected: tuple[str, ...], *,
                  player: int, destination: str, neutral_open_main: bool) -> tuple[MovingUnit, ...]:
    """144: effect-free movement validation, not combat/showdown initiation.

    Post-move cleanup/contested status/showdown MUST be scheduled by the caller.
    Ganking and other permission-changing effects are outside this primitive.
    """
    if not neutral_open_main or player not in (0, 1):
        raise ValueError("144.1: standard movement requires your Neutral Open Main Phase")
    if not selected or len(set(selected)) != len(selected):
        raise ValueError("choose a nonempty set of distinct units")
    by_id = {u.id: u for u in units}
    if len(by_id) != len(units) or any(key not in by_id for key in selected):
        raise ValueError("unknown or duplicate unit IDs")
    base = f"base:{player}"
    fields = {"battlefield:0", "battlefield:1"}
    for key in selected:
        unit = by_id[key]
        if unit.controller != player or unit.exhausted:
            raise ValueError("144.2: only controlled ready units can pay movement cost")
        if not ((unit.location == base and destination in fields)
                or (unit.location in fields and destination == base)):
            raise ValueError("144.4: standard movement is base-to-battlefield or battlefield-to-base")
    return tuple(MovingUnit(u.id, u.controller, destination, True) if u.id in selected else u for u in units)


@dataclass
class Scoreboard:
    """469–474 without triggered/replacement effects; caller handles returned draw."""

    points: list[int] = field(default_factory=lambda: [0, 0])
    scored: list[set[int]] = field(default_factory=lambda: [set(), set()])
    victory: int = 8
    battlefield_count: int = 2

    def new_turn(self) -> None:
        self.scored = [set(), set()]

    def score(self, player: int, battlefield: int, *, method: str) -> str:
        if player not in (0, 1) or not 0 <= battlefield < self.battlefield_count:
            raise ValueError("invalid player or battlefield")
        if method not in {"hold", "conquer"}:
            raise ValueError("unknown scoring method")
        if battlefield in self.scored[player]:
            return "already_scored"
        self.scored[player].add(battlefield)
        if (method == "conquer" and self.points[player] >= self.victory - 1
                and len(self.scored[player]) != self.battlefield_count):
            return "draw"  # 473.1.b.1; still Scored, triggers still occur.
        self.points[player] += 1
        return "point"

    def winner_at_cleanup(self) -> int | None:
        for player in (0, 1):
            if self.points[player] >= self.victory and self.points[player] > self.points[1-player]:
                return player
        return None


@dataclass(frozen=True)
class Unit:
    id: str
    might: int
    damage: int = 0

    def __post_init__(self):
        if not self.id or type(self.might) is not int or type(self.damage) is not int or self.damage < 0:
            raise ValueError("invalid unit")

    @property
    def lethal(self) -> bool:
        return self.damage > 0 and self.damage >= self.might  # 142.4.b includes 0 Might.


def damage_assignments(total: int, targets: tuple[Unit, ...]) -> tuple[tuple[int, ...], ...]:
    """467.2.c: all legal allocations for units WITHOUT assignment-altering effects.

    Lethal before the next target; overkill only after every target is lethal.
    Returned tuple aligns with target order. Intended for small skirmishes;
    factorial enumeration should be replaced before large-board training.
    """
    if type(total) is not int or total < 0 or not targets:
        raise ValueError("damage needs a nonnegative total and at least one target")
    if len({u.id for u in targets}) != len(targets) or any(u.lethal for u in targets):
        raise ValueError("targets need unique IDs and must have survived prior cleanup")
    allocations = set()
    for order in permutations(range(len(targets))):
        amounts, remaining = [0] * len(targets), total
        for index in order:
            lethal = max(1, targets[index].might) - targets[index].damage
            amount = min(remaining, lethal)
            amounts[index] += amount
            remaining -= amount
        # Excess can be put on any target once all other targets have lethal.
        if remaining:
            for index in range(len(targets)):
                overkill = amounts.copy()
                overkill[index] += remaining
                allocations.add(tuple(overkill))
        else:
            allocations.add(tuple(amounts))
    return tuple(sorted(allocations))


@dataclass(frozen=True)
class CombatResult:
    attacker_survivors: tuple[Unit, ...]
    defender_survivors: tuple[Unit, ...]
    killed: tuple[str, ...]
    recalled: tuple[str, ...]
    result: str  # attacker, defender, or no_result (468.3)


def resolve_combat(attackers: tuple[Unit, ...], defenders: tuple[Unit, ...],
                   attacker_assignment: tuple[int, ...], defender_assignment: tuple[int, ...]) -> CombatResult:
    """467–468 for effect-free units AFTER the combat showdown closes.

    Attacker chooses damage onto defenders, defender chooses onto attackers.
    No card triggers, prevention, shields, armor, tank, backline or other effects
    are supported by this primitive. Surviving units heal during combat cleanup.
    """
    if not attackers or not defenders or len({u.id for u in (*attackers, *defenders)}) != len(attackers)+len(defenders):
        raise ValueError("combat requires two nonempty sides with unique IDs")
    attack = sum(max(0, u.might) for u in attackers)
    defend = sum(max(0, u.might) for u in defenders)
    if attacker_assignment not in damage_assignments(attack, defenders):
        raise ValueError("illegal attacker damage allocation")
    if defender_assignment not in damage_assignments(defend, attackers):
        raise ValueError("illegal defender damage allocation")
    hit_attackers = tuple(Unit(u.id, u.might, u.damage+d) for u, d in zip(attackers, defender_assignment))
    hit_defenders = tuple(Unit(u.id, u.might, u.damage+d) for u, d in zip(defenders, attacker_assignment))
    killed = tuple(u.id for u in (*hit_attackers, *hit_defenders) if u.lethal)
    alive_a = tuple(Unit(u.id, u.might) for u in hit_attackers if not u.lethal)
    alive_d = tuple(Unit(u.id, u.might) for u in hit_defenders if not u.lethal)
    recalled = tuple(u.id for u in alive_a) if alive_d else ()
    result = "no_result" if recalled or (not alive_a and not alive_d) else ("attacker" if alive_a else "defender")
    return CombatResult(alive_a, alive_d, killed, recalled, result)
