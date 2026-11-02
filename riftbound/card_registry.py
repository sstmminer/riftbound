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
    combat_effect: str | None = None
    deathknell_effect: str | None = None
    spell_effect: str | None = None
    activated_effect: str | None = None
    target_scope: str | None = None
    target_min: int = 1
    target_max: int = 1
    buff_effect: str | None = None
    might_effect: str | None = None
    global_effect: str | None = None
    additional_cost_energy: int = 0
    additional_cost_power: int = 0
    additional_cost_effect: str | None = None
    cost_reduction_effect: str | None = None
    placement_rule: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.card_id or not self.set_code:
            raise ValueError("card implementation needs a namespaced ID and set")
        if self.status not in {"catalog-only", "executable"}:
            raise ValueError("unknown implementation status")
        if self.status == "executable" and not any((
                self.behavior_id, self.static_keywords, self.entry_effect,
                self.entry_trigger, self.move_effect, self.hold_effect,
                self.conquer_effect, self.combat_effect,
                self.deathknell_effect, self.spell_effect,
                self.activated_effect,
                self.buff_effect, self.might_effect, self.global_effect,
                self.additional_cost_effect, self.cost_reduction_effect,
                self.placement_rule)):
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
        CardImplementation("SFD-031-221", sfd, "spell", "executable",
                           spell_effect="play_sand_soldier",
                           notes="Play a Sand Soldier unit token."),
        CardImplementation("SFD-007-221", sfd, "unit", "executable",
                           entry_trigger="ganking_target",
                           notes="When played, choose a unit to give Ganking this turn."),
        CardImplementation("SFD-012-221", sfd, "unit", "executable",
                           cost_reduction_effect="cards_played_floor_one",
                           notes="Costs 1 less for each card played this turn, to a minimum of 1."),
        CardImplementation("SFD-014-221", sfd, "unit", "executable",
                           global_effect="no_base_moves",
                           notes="Units can't move to base while this is in play."),
        CardImplementation("SFD-028-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"assault_1"}),
                           entry_trigger=None,
                           notes="Assault 1; when attacking, deal Assault damage to an enemy here."),
        CardImplementation("SFD-015-221", sfd, "unit", "executable",
                           placement_rule="conquered_field_this_turn",
                           notes="May be played only to a battlefield conquered this turn."),
        CardImplementation("SFD-021-221", sfd, "unit", "executable",
                           deathknell_effect="play_two_mech",
                           notes="Deathknell; play two 3-Might Mech tokens to your base."),
        CardImplementation("SFD-093-221", sfd, "unit", "executable",
                           placement_rule="occupied_enemy_field",
                           notes="May be played to an occupied enemy battlefield."),
        CardImplementation("SFD-060-221", sfd, "unit", "executable",
                           global_effect="opponents_cant_score",
                           notes="Opponents can't gain points while this is at a battlefield."),
        CardImplementation("SFD-158-221", sfd, "unit", "executable",
                           entry_trigger="kill_small_enemy",
                           notes="When played, kill an enemy unit with Might 3 or less."),
        CardImplementation("SFD-034-221", sfd, "spell", "executable",
                           reaction=True, spell_effect="buff_two", target_scope="any_unit",
                           notes="Reaction; give a unit +2 Might this turn."),
        CardImplementation("SFD-066-221", sfd, "spell", "executable",
                           reaction=True, spell_effect="debuff_two", target_scope="any_unit",
                           notes="Reaction; give a unit -2 Might this turn."),
        CardImplementation("SFD-076-221", sfd, "spell", "executable",
                           spell_effect="play_mech_token_draw",
                           cost_reduction_effect="control_mech",
                           notes="Costs 2 less while controlling a Mech; play a Mech token and draw 1."),
        CardImplementation("SFD-089-221", sfd, "unit", "executable",
                           global_effect="mechs_plus_one",
                           hold_effect="play_mech_token",
                           notes="Your Mechs have +1 Might; when holding, play a 3-Might Mech token."),
        CardImplementation("SFD-131-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"accelerate"}),
                           might_effect="assault_by_enemy",
                           notes="Accelerate; has Assault equal to the number of enemy units here."),
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
        CardImplementation("SFD-046-221", sfd, "gear", "executable",
                           entry_trigger="draw_one", activated_effect="gear_draw",
                           notes="Play: draw 1; pay 1 Energy and Calm, exhaust and kill: draw 1."),
        CardImplementation("SFD-052-221", sfd, "gear", "executable",
                           activated_effect="gear_buff_three", target_scope="any_unit",
                           notes="Exhaust: give a unit +3 Might this turn."),
        CardImplementation("SFD-110-221", sfd, "unit", "executable",
                           might_effect="double_one_on_one",
                           notes="Doubles its Might in a one-on-one combat."),
        CardImplementation("SFD-116-221", sfd, "unit", "executable",
                           conquer_effect="damage_enemy_base_by_might",
                           notes="After conquering an uncontrolled battlefield, may damage an enemy unit in base."),
        CardImplementation("SFD-166-221", sfd, "spell", "executable",
                           spell_effect="rally_the_troops",
                           notes="Draw 1; friendly units played this turn enter with a buff."),
        CardImplementation("SFD-163-221", sfd, "spell", "executable",
                           spell_effect="deathgrip", target_scope="friendly_unit",
                           target_min=2, target_max=2,
                           notes="Kill one friendly unit, buff another by its Might, then draw 1."),
        CardImplementation("SFD-168-221", sfd, "gear", "executable",
                           activated_effect="play_three_recruit",
                           notes="Exhaust: play three Recruit tokens, choosing each destination."),
        CardImplementation("SFD-028A-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"assault_1"}),
                           notes="Alternate Lucian printing; Assault 1 and attack trigger."),
        CardImplementation("SFD-089A-221", sfd, "unit", "executable",
                           global_effect="mechs_plus_one", hold_effect="play_mech_token",
                           notes="Alternate Rumble, Scrapper printing."),
        CardImplementation("SFD-149A-221", sfd, "unit", "executable",
                           entry_trigger="discard_one_draw_two",
                           notes="Alternate Ezreal, Prodigy printing."),
        CardImplementation("SFD-003-221", sfd, "spell", "executable",
                           spell_effect="assault_two", target_scope="any_unit",
                           notes="Give a unit Assault 2 this turn."),
        CardImplementation("SFD-017-221", sfd, "spell", "executable",
                           spell_effect="sudden_storm", target_scope="field_unit",
                           notes="Deal 2 to a battlefield unit, or 4 if attacking."),
        CardImplementation("SFD-040-221", sfd, "spell", "executable",
                           spell_effect="stun_attacking", target_scope="attacking_unit",
                           notes="Stun an attacking unit."),
        CardImplementation("SFD-070-221", sfd, "spell", "executable",
                           spell_effect="wages_of_pain", target_scope="field_unit",
                           notes="Deal 3 to a battlefield unit, then create an exhausted Gold gear."),
        CardImplementation("SFD-100-221", sfd, "unit", "executable",
                           global_effect="draw_on_power_two",
                           notes="When you play a card with Power cost 2 or more, draw 1."),
        CardImplementation("SFD-123-221", sfd, "unit", "executable",
                           move_effect="discard_one", combat_effect="draw_one_on_win",
                           notes="Discard 1 when moving to a battlefield; draw 1 when winning combat."),
        CardImplementation("SFD-151-221", sfd, "spell", "executable",
                           reaction=True, spell_effect="buff_two_each",
                           target_scope="friendly_unit", target_min=2, target_max=2,
                           notes="Give two friendly units +1 Might this turn."),
        CardImplementation("SFD-181-221", sfd, "legend", "executable",
                           global_effect="mechs_shield",
                           notes="Your Mechs have Shield."),
        CardImplementation("SFD-041-221", sfd, "unit", "executable",
                           move_effect="apprentice_smith",
                           notes="When moving, reveal the top card; draw it if it is Gear, otherwise recycle it."),
        CardImplementation("SFD-104-221", sfd, "gear", "executable",
                           global_effect="friendly_deflect",
                           notes="Temporary; friendly units have Deflect."),
        CardImplementation("SFD-171A-221", sfd, "unit", "executable",
                           global_effect="tokens_enter_ready",
                           notes="Alternate Renata Glasc, Industrialist printing."),
        CardImplementation("SFD-227-221", sfd, "unit", "executable",
                           combat_effect="ahri_debuff",
                           notes="Ahri, Inquisitive combat trigger."),
        CardImplementation("SFD-227-STAR-221", sfd, "unit", "executable",
                           combat_effect="ahri_debuff",
                           notes="Alternate Ahri, Inquisitive printing."),
        CardImplementation("SFD-235-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"ganking"}),
                           move_effect="score_on_third_move",
                           notes="Yasuo, Windrider; score on the third move each turn."),
        CardImplementation("SFD-235-STAR-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"ganking"}),
                           move_effect="score_on_third_move",
                           notes="Alternate Yasuo, Windrider printing."),
        CardImplementation("SFD-236-221", sfd, "unit", "executable",
                           entry_effect="enter_ready_if_legion",
                           global_effect="plus_one_friendly_here",
                           notes="Darius, Executioner; Legion and local friendly +1 Might."),
        CardImplementation("SFD-236-STAR-221", sfd, "unit", "executable",
                           entry_effect="enter_ready_if_legion",
                           global_effect="plus_one_friendly_here",
                           notes="Alternate Darius, Executioner printing."),
        CardImplementation("SFD-237-221", sfd, "unit", "executable",
                           global_effect="vision_recycle",
                           notes="Karma, Channeler; Vision and recycle trigger."),
        CardImplementation("SFD-237-STAR-221", sfd, "unit", "executable",
                           global_effect="vision_recycle",
                           notes="Alternate Karma, Channeler printing."),
        CardImplementation("SFD-240-221", sfd, "legend", "executable",
                           global_effect="mechs_shield",
                           notes="Alternate Mechanized Menace printing."),
        CardImplementation("SFD-242-221", sfd, "legend", "executable",
                           combat_effect="draw_one_on_win",
                           notes="Glorious Executioner draws after a combat win."),
        CardImplementation("SFD-055-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"tank", "shield_5"}),
                           cost_reduction_effect="hold_points",
                           notes="Needlessly Large Yordle; Shield 5, Tank, and hold-point cost reduction."),
        CardImplementation("SFD-223-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"assault_3"}),
                           entry_effect="enter_ready_if_opponent_field",
                           conquer_effect="return_self",
                           notes="Vayne, Hunter; Assault 3, conditional ready, and optional paid recall."),
        CardImplementation("SFD-223-STAR-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"assault_3"}),
                           entry_effect="enter_ready_if_opponent_field",
                           conquer_effect="return_self",
                           notes="Alternate Vayne, Hunter printing."),
        CardImplementation("SFD-230-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"hidden"}), global_effect="teemo_defend",
                           notes="Teemo, Strategist; Hidden defend trigger uses the shared five-card reveal."),
        CardImplementation("SFD-230-STAR-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"hidden"}), global_effect="teemo_defend",
                           notes="Alternate Teemo, Strategist printing."),
        CardImplementation("SFD-232-221", sfd, "unit", "executable",
                           entry_trigger="buff_self", conquer_effect="buff_self",
                           activated_effect="spend_buff_four",
                           notes="Sett, Brawler; play/conquer buff and generic buff-spend activation."),
        CardImplementation("SFD-232-STAR-221", sfd, "unit", "executable",
                           entry_trigger="buff_self", conquer_effect="buff_self",
                           activated_effect="spend_buff_four",
                           notes="Alternate Sett, Brawler printing."),
        CardImplementation("SFD-185-221", sfd, "legend", "executable",
                           combat_effect="draw_one_on_win",
                           notes="Glorious Executioner; normal printing."),
        CardImplementation("SFD-105-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"untargetable_enemy"}),
                           notes="Ruin Runner; enemy target windows exclude this unit."),
        CardImplementation("SFD-204-221", sfd, "spell", "executable",
                           spell_effect="ready_friendly_units",
                           notes="On the Hunt; ready all friendly units through the shared ready path."),
        CardImplementation("SFD-110A-221", sfd, "unit", "executable",
                           might_effect="double_one_on_one",
                           notes="Alternate Fiora, Peerless printing."),
        CardImplementation("SFD-233-221", sfd, "unit", "executable",
                           conquer_effect="damage_enemy_base_by_might",
                           notes="Yone, Blademaster; shared conquer damage trigger."),
        CardImplementation("SFD-233-STAR-221", sfd, "unit", "executable",
                           conquer_effect="damage_enemy_base_by_might",
                           notes="Alternate Yone, Blademaster printing."),
        CardImplementation("SFD-044-221", sfd, "unit", "executable",
                           additional_cost_effect="return_gear",
                           notes="Legion Quartermaster; return a friendly Gear as an additional cost."),
        CardImplementation("SFD-132-221", sfd, "unit", "executable",
                           entry_trigger="return_friendly_enemy",
                           notes="Beast Below; return another friendly unit and an enemy unit to their owners' hands."),
        CardImplementation("SFD-004-221", sfd, "spell", "executable",
                           static_keywords=frozenset({"hidden"}),
                           spell_effect="ready_friendly_and_gold",
                           notes="Bushwhack; friendly units played this turn enter ready and create an exhausted Gold gear."),
        CardImplementation("SFD-122-221", sfd, "spell", "executable",
                           spell_effect="draw_one_recycle_one",
                           notes="Called Shot; reveal the top two, draw one, and recycle the other through the shared reveal window."),
        CardImplementation("SFD-138-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"hidden"}),
                           entry_trigger="optional_return_small_field_unit",
                           notes="Windsinger; may return another battlefield unit with Might 3 or less."),
        CardImplementation("SFD-126-221", sfd, "unit", "executable",
                           combat_effect="loyal_pup_defend",
                           notes="Loyal Pup; while defending, may move from base to the defending battlefield."),
        CardImplementation("SFD-128-221", sfd, "unit", "executable",
                           combat_effect="overzealous_fan_defend",
                           notes="Overzealous Fan; while defending, may die to recall an attacking unit."),
        CardImplementation("SFD-189-221", sfd, "legend", "executable", reaction=True,
                           activated_effect="legend_rainbow",
                           notes="Fire Below the Mountain; exhaust as a Reaction to add a Rainbow rune power for Gear."),
        CardImplementation("SFD-244-221", sfd, "legend", "executable", reaction=True,
                           activated_effect="legend_rainbow",
                           notes="Fire Below the Mountain alternate printing; shared Legend resource ability."),
        CardImplementation("SFD-192-221", sfd, "gear", "executable",
                           entry_trigger="ready_friendly_units",
                           notes="Shurelya's Requiem; when played, ready all friendly units."),
        CardImplementation("SFD-020-221", sfd, "unit", "executable",
                           combat_effect="play_gold_gear",
                           global_effect="draven_combat_might",
                           notes="Draven, Vanquisher; creates Gold after winning combat and may pay Rainbow for +2 Might."),
        CardImplementation("SFD-020A-221", sfd, "unit", "executable",
                           combat_effect="play_gold_gear",
                           global_effect="draven_combat_might",
                           notes="Alternate Draven, Vanquisher printing; shared combat and optional Might hooks."),
        CardImplementation("SFD-196-221", sfd, "spell", "executable", reaction=True,
                           spell_effect="buff_debuff_pair", target_scope="any_unit",
                           target_min=2, target_max=2,
                           notes="Defiant Dance; choose two distinct units, then apply +2 and -2 in order."),
        CardImplementation("SFD-194-221", sfd, "spell", "executable", reaction=True,
                           spell_effect="prevent_next_damage_draw", target_scope="any_unit",
                           notes="Counter Strike; prevent the next damage to a unit this turn and draw 1."),
        CardImplementation("SFD-013-221", sfd, "unit", "executable",
                           additional_cost_energy=1,
                           additional_cost_effect="blast_corps",
                           notes="Blast Corps Cadet; optional extra payment opens a battlefield-unit damage target."),
        CardImplementation("SFD-067-221", sfd, "unit", "executable",
                           additional_cost_power=1,
                           additional_cost_effect="frostcoat_debuff",
                           notes="Frostcoat Cub; optional extra Mind power opens a unit -2 Might target."),
    ])
