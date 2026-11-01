"""Namespaced card implementation registry.

Card text is catalog data; it never becomes executable by being present in the
gallery snapshot.  A set adapter must register an explicit implementation and
its tested hooks.  This keeps future sets out of Origins' code-number branches
until the required timing and target windows are implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class CardImplementation:
    card_id: str
    set_code: str
    kind: str
    status: str = "catalog-only"
    reaction: bool = False
    behavior_id: str | None = None
    static_keywords: frozenset[str] = frozenset()
    entry_effect: str | None = None
    entry_trigger: str | None = None
    move_effect: str | None = None
    hold_effect: str | None = None
    conquer_effect: str | None = None
    deathknell_effect: str | None = None
    spell_effect: str | None = None
    target_scope: str | None = None
    target_min: int = 1
    target_max: int = 1
    buff_effect: str | None = None
    might_effect: str | None = None
    global_effect: str | None = None
    additional_cost_energy: int = 0
    additional_cost_effect: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.card_id or not self.set_code:
            raise ValueError("card implementation needs a namespaced ID and set")
        if self.status not in {"catalog-only", "executable"}:
            raise ValueError("unknown implementation status")
        if self.status == "executable" and not any((
                self.behavior_id, self.static_keywords, self.entry_effect,
                self.entry_trigger, self.move_effect, self.hold_effect,
                self.conquer_effect,
                self.deathknell_effect, self.spell_effect,
                self.buff_effect, self.might_effect, self.global_effect,
                self.additional_cost_effect)):
            raise ValueError("executable implementation needs an explicit hook")


class CardSetRegistry:
    """Immutable-by-convention registry merged by set adapters."""

    def __init__(self, implementations: Iterable[CardImplementation] = ()) -> None:
        self._items: dict[str, CardImplementation] = {}
        for item in implementations:
            self.register(item)

    def register(self, item: CardImplementation) -> None:
        if item.card_id in self._items:
            raise ValueError(f"card implementation already registered: {item.card_id}")
        self._items[item.card_id] = item

    def merge(self, other: "CardSetRegistry") -> "CardSetRegistry":
        merged = CardSetRegistry(self._items.values())
        for item in other._items.values():
            merged.register(item)
        return merged

    def get(self, card_id: str) -> CardImplementation | None:
        return self._items.get(card_id)

    def is_executable(self, card_id: str) -> bool:
        item = self.get(card_id)
        return item is not None and item.status == "executable"

    def behavior_id(self, card_id: str) -> str:
        item = self.get(card_id)
        return item.behavior_id if item and item.behavior_id else card_id

    def executable_codes(self, *, kind: str | None = None) -> frozenset[str]:
        return frozenset(item.card_id for item in self._items.values()
                         if item.status == "executable"
                         and (kind is None or item.kind == kind))

    def implementations(self) -> tuple[CardImplementation, ...]:
        return tuple(self._items[key] for key in sorted(self._items))


def spiritforged_registry() -> CardSetRegistry:
    """First conservative executable SFD cluster.

    These cards use existing rule primitives or one explicit registered spell
    handler.  More complex Weaponmaster/Equipment, Repeat, Hidden, and nested
    free-play cards remain catalog-only until their shared infrastructure is
    complete; they are never allowed to silently fizzle through a generic path.
    """

    sfd = "SFD"
    return CardSetRegistry([
        CardImplementation("SFD-006-221", sfd, "unit", "executable",
                           entry_effect="enter_ready",
                           notes="I enter ready."),
        CardImplementation("SFD-037-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"deflect"}),
                           notes="Deflect; same keyword predicate as Origins."),
        CardImplementation("SFD-222-221", sfd, "gear", "executable",
                           behavior_id="OGN-040", notes="Seal of Rage resource ability."),
        CardImplementation("SFD-226-221", sfd, "gear", "executable",
                           behavior_id="OGN-081", notes="Seal of Focus resource ability."),
        CardImplementation("SFD-229-221", sfd, "gear", "executable",
                           behavior_id="OGN-120", notes="Seal of Insight resource ability."),
        CardImplementation("SFD-231-221", sfd, "gear", "executable",
                           behavior_id="OGN-163", notes="Seal of Strength resource ability."),
        CardImplementation("SFD-234-221", sfd, "gear", "executable",
                           behavior_id="OGN-204", notes="Seal of Discord resource ability."),
        CardImplementation("SFD-238-221", sfd, "gear", "executable",
                           behavior_id="OGN-245", notes="Seal of Unity resource ability."),
        CardImplementation("SFD-096-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"ganking"}),
                           notes="Ganking."),
        CardImplementation("SFD-156-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"assault_2"}),
                           notes="Assault 2."),
        CardImplementation("SFD-176-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"tank"}),
                           entry_effect="enter_ready_if_base_units",
                           notes="Tank; enters ready with two other units in base."),
        CardImplementation("SFD-087-221", sfd, "spell", "executable",
                           reaction=True, spell_effect="draw_three",
                           notes="Reaction; draw 3."),
        CardImplementation("SFD-036-221", sfd, "unit", "executable",
                           deathknell_effect="draw_if_alone",
                           notes="Deathknell; draw if this unit died alone."),
        CardImplementation("SFD-048-221", sfd, "unit", "executable",
                           move_effect="draw_one",
                           notes="When this unit moves, draw 1."),
        CardImplementation("SFD-094-221", sfd, "unit", "executable",
                           entry_effect="enter_ready_if_dragon",
                           notes="Enters ready if you control another Dragon."),
        CardImplementation("SFD-106-221", sfd, "spell", "executable",
                           reaction=True, spell_effect="draw_mighty",
                           notes="Reaction; draw for each Mighty unit."),
        CardImplementation("SFD-147-221", sfd, "spell", "executable",
                           spell_effect="return_all_units_gear",
                           notes="Return all units and gear to their owners' hands."),
        CardImplementation("SFD-001-221", sfd, "spell", "executable",
                           reaction=True, spell_effect="buff_by_enemy",
                           target_scope="friendly_field_unit",
                           notes="Give a friendly battlefield unit +2 Might per enemy there."),
        CardImplementation("SFD-005-221", sfd, "spell", "executable",
                           spell_effect="kill_gear_draw_two", target_scope="any_gear",
                           notes="Kill a gear; its controller draws two."),
        CardImplementation("SFD-097-221", sfd, "spell", "executable",
                           spell_effect="buff_five", target_scope="any_unit",
                           notes="Give a unit +5 Might this turn."),
        CardImplementation("SFD-135-221", sfd, "spell", "executable",
                           spell_effect="return_gear", target_scope="any_gear",
                           notes="Return a gear to its owner's hand."),
        CardImplementation("SFD-155-221", sfd, "unit", "executable",
                           deathknell_effect="play_gold_gear",
                           notes="Deathknell; play an exhausted Gold gear token."),
        CardImplementation("SFD-047-221", sfd, "unit", "executable",
                           buff_effect="ready_self",
                           notes="When buffed, ready this unit."),
        CardImplementation("SFD-072-221", sfd, "unit", "executable",
                           entry_effect="enter_ready_if_two_gear",
                           notes="Enters ready if you control two or more gear."),
        CardImplementation("SFD-130-221", sfd, "unit", "executable",
                           move_effect="play_gold_gear",
                           notes="When this unit moves, play an exhausted Gold gear token."),
        CardImplementation("SFD-137-221", sfd, "unit", "executable",
                           move_effect="buff_self_two_from_field",
                           notes="When this unit moves from a battlefield, get +2 Might this turn."),
        CardImplementation("SFD-159-221", sfd, "unit", "executable",
                           might_effect="plus_one_if_another_friendly_here",
                           notes="Gets +1 Might while you have another unit here."),
        CardImplementation("SFD-167-221", sfd, "unit", "executable",
                           deathknell_effect="draw_two_if_mighty",
                           notes="Deathknell; if this was Mighty, draw 2."),
        CardImplementation("SFD-027-221", sfd, "unit", "executable",
                           entry_effect="enter_ready_if_small_hand",
                           hold_effect="draw_two",
                           notes="Enters ready with two or fewer cards in hand; draw 2 when holding."),
        CardImplementation("SFD-061-221", sfd, "unit", "executable",
                           entry_trigger="return_gear_from_trash",
                           notes="When played, choose a gear in your trash and return it to hand."),
        CardImplementation("SFD-062-221", sfd, "unit", "executable",
                           entry_trigger="ready_another_friendly_mech",
                           notes="When played, choose another friendly Mech and ready it."),
        CardImplementation("SFD-152-221", sfd, "unit", "executable",
                           hold_effect="play_two_gold_gear",
                           notes="When holding, play two exhausted Gold gear tokens."),
        CardImplementation("SFD-171-221", sfd, "unit", "executable",
                           global_effect="tokens_enter_ready",
                           notes="Your tokens enter ready."),
        CardImplementation("SFD-174-221", sfd, "unit", "executable",
                           entry_trigger="play_four_gold_gear",
                           notes="When played, play four exhausted Gold gear tokens."),
        CardImplementation("SFD-098-221", sfd, "unit", "executable",
                           additional_cost_energy=1,
                           additional_cost_effect="buff_self",
                           notes="May pay 1 additional Energy; if paid, buff this unit."),
        CardImplementation("SFD-032-221", sfd, "unit", "executable",
                           entry_trigger="optional_kill_gear",
                           notes="When played, optionally kill a gear."),
        CardImplementation("SFD-035-221", sfd, "unit", "executable",
                           hold_effect="optional_return_card_from_trash",
                           notes="When holding, optionally return a unit or gear from trash."),
        CardImplementation("SFD-038-221", sfd, "unit", "executable",
                           move_effect="buff_another_on_move",
                           notes="When moving to a battlefield, buff another friendly unit there."),
        CardImplementation("SFD-039-221", sfd, "unit", "executable",
                           entry_trigger="legend_toggle",
                           notes="When played, choose to ready or exhaust a legend."),
        CardImplementation("SFD-071-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"deflect", "ganking"}),
                           global_effect="mechs_deflect_ganking",
                           entry_effect="enter_ready_if_another_mech",
                           notes="Mechs have Deflect and Ganking; enters ready with another Mech."),
        CardImplementation("SFD-065-221", sfd, "unit", "executable",
                           global_effect="mechs_vision",
                           notes="Your Mechs have Vision."),
        CardImplementation("SFD-069-221", sfd, "unit", "executable",
                           conquer_effect="play_gold_gear",
                           notes="When this conquers, play an exhausted Gold gear token."),
        CardImplementation("SFD-074-221", sfd, "unit", "executable",
                           entry_trigger="optional_kill_cheap_gear",
                           notes="When played, may kill a gear costing 1 or less, then play an exhausted Gold gear token."),
        CardImplementation("SFD-075-221", sfd, "unit", "executable",
                           global_effect="prize_progress",
                           notes="When you use an activated gear ability, this gets +1 Might this turn."),
        CardImplementation("SFD-091-221", sfd, "unit", "executable",
                           entry_trigger="optional_draw_or_buff",
                           notes="When played, optionally draw 1 or buff this unit."),
        CardImplementation("SFD-149-221", sfd, "unit", "executable",
                           entry_trigger="discard_one_draw_two",
                           notes="When played, discard 1, then draw 2."),
        CardImplementation("SFD-157-221", sfd, "unit", "executable",
                           entry_trigger="play_sand_soldier",
                           notes="When played, play a 2-Might Sand Soldier here."),
        CardImplementation("SFD-162-221", sfd, "spell", "executable",
                           spell_effect="kill_small_unit_and_gold",
                           target_scope="field_unit_might_le_2",
                           notes="Kill a battlefield unit with Might 2 or less; make Gold based on controller."),
        CardImplementation("SFD-175-221", sfd, "unit", "executable",
                           entry_trigger="buff_other_units_two",
                           notes="When played, give other friendly units +2 Might this turn."),
        CardImplementation("SFD-179-221", sfd, "unit", "executable",
                           move_effect="play_recruit_three",
                           notes="When moving to a battlefield, play three Recruit tokens there."),
    ])
