"""Executable Origins subset. RUP5, 2026-10-09; pinned archive text/errata.

No text interpretation or fallback effects: construction rejects unregistered
cards. This backend covers only the card set in support.py, not full Origins.
"""
from __future__ import annotations

from collections import Counter
import copy
import hashlib
from itertools import combinations, permutations
import json
import random

from .catalog import load_origins, require_supported
from .core import DOMAINS, Card, Deck, Scoreboard, Unit, channel_count, draw_cards, mulligan, validate_deck
from .engine import Action, RulesUnavailable, canonical
from .effects import EffectRegistry
from .abilities import ORIGINS_ABILITIES
from .card_registry import CardSetRegistry
from .support import ACCELERATE, FIELD_CODES, GEAR_CODES, HIDDEN_CODES, LEGENDS, REACTIONS, RUNES, SPELL_CODES, SPRITE_TOKEN, TOKEN, UNIT_CODES, SUPPORTED, starter_deck

# Spells with one ordinary unit target and no destination/pairing choice can
# use the same click-to-select target window as the repeated-target spells.
# Legacy expanded actions remain available to non-GUI policies for replay
# compatibility; the GUI can prefer the targeted variant.
SIMPLE_TARGET_SPELLS = frozenset({
    "OGN-004", "OGN-005", "OGN-009", "OGN-014", "OGN-024", "OGN-033",
    "OGN-046", "OGN-050", "OGN-057", "OGN-058", "OGN-069", "OGN-085",
    "OGN-093", "OGN-095", "OGN-102", "OGN-146", "OGN-154",
    "OGN-169", "OGN-172", "OGN-203", "OGN-207", "OGN-213",
    "OGN-008", "OGN-168", "OGN-180", "OGN-229", "OGN-252", "OGN-254", "OGN-262",
    "OGN-053",
})
PAIR_TARGET_SPELLS = frozenset({"OGN-108", "OGN-128", "OGN-209", "OGN-220", "OGN-260"})
DESTINATION_TARGET_SPELLS = frozenset({"OGN-043", "OGN-173", "OGN-250", "OGN-270", "OGN-258"})
OPTIONAL_TARGET_SPELLS = frozenset({"OGN-048"})
CONSTRAINED_MULTI_TARGET_SPELLS = frozenset({"OGN-256"})
FIELD_TARGET_SPELLS = frozenset({"OGN-266"})
SEQUENTIAL_TARGET_SPELLS = frozenset({"OGN-258"})


def card_model(row):
    return Card(row["code"], row["name"], row["type"], frozenset(row["domains"]),
                frozenset(row["tags"]), row["champion"], row["signature"],
                rules_text=row["text"])


class OriginsRules:
    def __init__(self, decks=None, *, extra_fields=(), card_registry=None,
                 additional_cards=()):
        self.cards = {row["code"]: row for row in load_origins()}
        self.card_registry = card_registry or CardSetRegistry()
        for row in additional_cards:
            # Expansion rows use a stable official-print ``id``.  The rules
            # backend uses ``code`` for all physical cards, so normalize only
            # at this adapter boundary and retain the original ID verbatim.
            code = row.get("code", row.get("id"))
            if not code:
                raise ValueError("additional card rows require id or code")
            if code in self.cards:
                raise ValueError(f"duplicate card code: {code}")
            self.cards[code] = {**row, "code": code}
        # Declarative activated-ability registry. The same table drives ordinary
        # source discovery and Heimerdinger's exhaust-only copy.
        self.abilities = ORIGINS_ABILITIES
        self.ability_registry = self.abilities
        self.effects = self._build_effect_registry()
        self.extra_fields = list(extra_fields)
        if len(self.extra_fields) > 4 or not set(self.extra_fields) <= FIELD_CODES:
            raise ValueError("extra_fields must contain at most four supported battlefield codes")
        self.decks = copy.deepcopy(decks if decks is not None else [starter_deck(), starter_deck()])
        if len(self.decks) != 2:
            raise ValueError("exactly two decks required")
        models = {code: card_model(row) for code, row in self.cards.items()
                  if row.get("type") in {"unit", "gear", "spell", "rune", "legend", "battlefield"}}
        for deck in self.decks:
            validate_deck(Deck(deck["legend"], deck["chosen_champion"], tuple(deck["main"]),
                               tuple(deck["runes"]), tuple(deck["battlefields"])), models)
            deck_codes = tuple([deck["legend"], *deck["main"], *deck["runes"], *deck["battlefields"]])
            unknown = set(deck_codes) - set(self.cards)
            if unknown:
                raise ValueError(f"unknown card IDs: {sorted(unknown)}")
            unsupported = {code for code in deck_codes
                           if code not in SUPPORTED and not self.card_registry.is_executable(code)}
            if unsupported:
                raise RulesUnavailable(f"Unsupported cards: {sorted(unsupported)}")
            if (deck["legend"] not in LEGENDS
                    and not self._is_executable_kind(deck["legend"], "legend")):
                raise ValueError("deck contains unsupported legend")
            if (not set(deck["runes"]) <= RUNES
                    and not all(self._is_executable_kind(code, "rune") for code in deck["runes"] if code not in RUNES)):
                raise ValueError("deck contains unsupported runes")
            if (not set(deck["battlefields"]) <= FIELD_CODES
                    and not all(self._is_executable_kind(code, "battlefield")
                                for code in deck["battlefields"] if code not in FIELD_CODES)):
                raise ValueError("deck contains unsupported legend, rune or battlefield")
            if any(self.cards[code]["token"] for code in deck["main"]):
                raise ValueError("tokens cannot be included in a constructed main deck")
        digest = hashlib.sha256(canonical({"cards": list(self.cards.values()), "decks": self.decks,
                                           "extra_fields": self.extra_fields}).encode()).hexdigest()
        registry_digest = canonical([
            {**item.__dict__, "static_keywords": sorted(item.static_keywords)}
            for item in self.card_registry.implementations()
        ])
        registry_hash = hashlib.sha256(registry_digest.encode()).hexdigest()
        registry_suffix = f"/{registry_hash}" if self.card_registry.implementations() else ""
        self.id = f"origins-subset/0.3.0/RUP5-2026-10-09/{digest}{registry_suffix}"

    def _card_implementation(self, code):
        return self.card_registry.get(code)

    def _is_executable_kind(self, code, kind):
        if code in SUPPORTED:
            return self.cards.get(code, {}).get("type") == kind
        implementation = self._card_implementation(code)
        return bool(implementation and implementation.status == "executable"
                    and implementation.kind == kind)

    def _behavior_code(self, code):
        return self.card_registry.behavior_id(code)

    def _has_static_keyword(self, code, keyword):
        implementation = self._card_implementation(code)
        return bool(implementation and keyword in implementation.static_keywords)

    def _is_accelerate_code(self, code):
        return code in ACCELERATE or self._has_static_keyword(code, "accelerate")

    def _is_hidden_code(self, code):
        return code in HIDDEN_CODES or self._has_static_keyword(code, "hidden")

    def _is_targetable(self, state, chooser, target_id):
        """Apply shared target-immunity predicates to unit target windows."""
        target = self._unit(state, target_id)
        if target is None:
            return True
        return not (target["owner"] != chooser
                    and self._has_static_keyword(target["code"], "untargetable_enemy"))

    def _is_reaction_code(self, code):
        implementation = self._card_implementation(code)
        return code in REACTIONS or bool(implementation and implementation.reaction)

    def _entry_ready(self, state, code, player):
        """Resolve explicit ready-at-entry declarations for any card set."""
        if self._card_implementation(code) is not None:
            effect = self._card_implementation(code).entry_effect
            if effect == "enter_ready":
                return True
            if effect == "enter_ready_if_base_units":
                return sum(unit["owner"] == player and unit["location"] == f"base:{player}"
                           for unit in state["units"]) >= 2
            if effect == "enter_ready_if_two_gear":
                return len(state["players"][player].get("gear", [])) >= 2
            if effect == "enter_ready_if_small_hand":
                return len(state["players"][player].get("hand", [])) <= 2
            if effect == "enter_ready_if_legion":
                return self._played_for_legion(state, player) > 0
            if effect == "enter_ready_if_opponent_field":
                return any(field["controller"] == 1 - player for field in state["fields"])
            if effect == "enter_ready_if_dragon":
                return any(
                    unit["owner"] == player
                    and "Dragon" in self.cards.get(unit["code"], {}).get("tags", [])
                    for unit in state["units"]
                )
            if effect == "enter_ready_if_another_mech":
                return any(
                    unit["owner"] == player
                    and "Mech" in self.cards.get(unit["code"], {}).get("tags", [])
                    for unit in state["units"]
                )
        return False

    def _build_effect_registry(self):
        """Register every chain effect implemented by this backend explicitly."""

        registry = EffectRegistry()
        registry.register("darius", self._effect_darius)
        registry.register("buff_self", self._effect_buff_self)
        registry.register("ravenbloom", self._effect_ravenbloom)
        registry.register("ahri_debuff", self._effect_ahri_debuff)
        registry.register("crackshot_target", self._effect_crackshot_target)
        registry.register("leona_stun_target", self._effect_leona_stun_target)
        registry.register("yasuo_attack_target", self._effect_yasuo_attack_target)
        registry.register("riptide_damage", self._effect_riptide_damage)
        registry.register("fae_debuff", self._effect_fae_debuff)
        registry.register("return_field_unit", self._effect_return_field_unit)
        registry.register("return_friendly_enemy", self._effect_return_friendly_enemy)
        registry.register("optional_return_small_field_unit", self._effect_optional_return_small_field_unit)
        registry.register("loyal_pup_defend", self._effect_loyal_pup_defend)
        registry.register("overzealous_fan_defend", self._effect_overzealous_fan_defend)
        registry.register("ready_friendly_units", self._effect_ready_friendly_units)
        registry.register("draven_might", self._effect_draven_might)
        registry.register("move_field_unit", self._effect_move_field_unit)
        registry.register("poro_herder", self._effect_poro_herder)
        registry.register("sprite_mother", self._effect_sprite_mother)
        registry.register("watcher_debuff", self._effect_watcher_debuff)
        registry.register("buff_self_three", self._effect_buff_self_three)
        registry.register("viktor_innovator", self._effect_viktor_innovator)
        registry.register("kadregrin_draw", self._effect_kadregrin_draw)
        registry.register("portal_rescue", self._effect_portal_rescue)
        registry.register("snapvine_fight", self._effect_snapvine_fight)
        registry.register("gear_debuff", self._effect_gear_debuff)
        registry.register("gear_buff_exhausted", self._effect_gear_buff_exhausted)
        registry.register("gear_move", self._effect_gear_move)
        registry.register("gear_damage", self._effect_gear_damage)
        registry.register("gear_return", self._effect_gear_return)
        registry.register("gear_buff_three", self._effect_gear_buff_three)
        registry.register("gear_draw", self._effect_gear_draw)
        registry.register("gear_armory_protect", self._effect_gear_armory_protect)
        registry.register("gear_baited_hook", self._effect_gear_baited_hook)
        registry.register("spirit_refuge", self._effect_spirit_refuge)
        registry.register("mindsplitter", self._effect_mindsplitter)
        registry.register("vanguard_helm", self._effect_vanguard_helm)
        registry.register("baited_hook_finish", self._effect_baited_hook_finish)
        registry.register("dazzling_aurora_continue", self._effect_dazzling_aurora_continue)
        registry.register("peak", self._effect_peak)
        registry.register("drummer", self._effect_drummer)
        registry.register("vision", self._effect_vision)
        registry.register("discard_two", self._effect_discard_two)
        registry.register("discard_one", self._effect_discard_one)
        registry.register("kill_target", self._effect_kill_target)
        registry.register("stun_target", self._effect_stun_target)
        registry.register("buff_eight", self._effect_buff_eight)
        registry.register("ready_target", self._effect_ready_target)
        registry.register("buff_target", self._effect_buff_target)
        registry.register("buff_two", self._effect_buff_two)
        registry.register("kinkou_buff", self._effect_kinkou_buff)
        registry.register("albus_optional", self._effect_albus_optional)
        registry.register("albus_channel", self._effect_albus_channel)
        registry.register("jinx_discard", self._effect_jinx_discard)
        registry.register("karma_recycle", self._effect_karma_recycle)
        registry.register("sabotage", self._effect_sabotage)
        registry.register("wildclaw_optional", self._effect_wildclaw_optional)
        registry.register("wildclaw_ready", self._effect_wildclaw_ready)
        registry.register("return_unit_trigger", self._effect_return_unit_trigger)
        registry.register("return_gear_from_trash", self._effect_return_gear_from_trash)
        registry.register("ready_another_friendly_mech", self._effect_ready_another_friendly_mech)
        registry.register("play_four_gold_gear", self._effect_play_four_gold_gear)
        registry.register("optional_kill_gear", self._effect_optional_kill_gear)
        registry.register("optional_kill_cheap_gear", self._effect_optional_kill_cheap_gear)
        registry.register("ganking_target", self._effect_ganking_target)
        registry.register("kill_small_enemy", self._effect_kill_small_enemy)
        registry.register("blast_corps", self._effect_blast_corps)
        registry.register("frostcoat_debuff", self._effect_frostcoat_debuff)
        registry.register("lucian_attack", self._effect_lucian_attack)
        registry.register("buff_another_on_move", self._effect_buff_another_on_move)
        registry.register("legend_toggle", self._effect_legend_toggle)
        registry.register("optional_draw_or_buff", self._effect_optional_draw_or_buff)
        registry.register("discard_one_draw_two", self._effect_discard_one_draw_two)
        registry.register("apprentice_smith", self._effect_apprentice_smith)
        registry.register("yordle_explorer", self._effect_yordle_explorer)
        registry.register("play_sand_soldier", self._effect_play_sand_soldier)
        registry.register("kill_small_unit_and_gold", self._effect_kill_small_unit_and_gold)
        registry.register("buff_other_units_two", self._effect_buff_other_units_two)
        registry.register("tideturner_target", self._effect_tideturner_target)
        registry.register("ember_hidden_buff", self._effect_ember_hidden_buff)
        registry.register("karthus_deathknell", self._effect_karthus_deathknell)
        registry.register("solari_target", self._effect_solari_target)
        registry.register("ready_self", self._effect_ready_self)
        registry.register("twisted_fate", self._effect_twisted_fate)
        registry.register("volibear_attack", self._effect_volibear_attack)
        registry.register("teemo_defend", self._effect_teemo_defend)
        registry.register("ava_attack", self._effect_ava_attack)
        registry.register("draw_one", self._effect_draw_one)
        registry.register("channel_one", self._effect_channel_one)
        registry.register("reaver_recall_target", self._effect_reaver_recall_target)
        registry.register("fortified_shield", self._effect_fortified_shield)
        registry.register("blitz_move", self._effect_blitz_move)
        registry.register("adaptatron_conquer", self._effect_adaptatron_conquer)
        registry.register("return_unit", self._effect_return_unit)
        registry.register("harrowing_finish", self._effect_harrowing_finish)
        registry.register("spell", self._effect_spell)
        registry.register("counter", self._effect_counter)
        return registry

    def initial_state(self, rng):
        first = rng.randrange(2)
        state = {"first": first, "turn_player": first, "actor": first, "turn": 0,
                 "phase": "mulligan", "mulligans": 0, "players": [], "cards": {},
                 "units": [], "fields": [], "points": [0, 0], "hold_points": [0, 0], "scored": [[], []],
                 "chain": [], "pending": [], "passes": 0, "battle": None,
                 "beginning_awarded": [False, False], "dreaming_tree_used": [], "selection": None,
                 "decision": None, "optional": [], "optional_return": None,
                 "reveal": None,
                 "optional_ordered": False, "pending_showdown": False,
                 "legend_options": [], "rune_undo": [], "winner": None, "next_object": 0}
        state["flame_chompers_offered"] = []
        state["prevent_spell_ability_damage"] = False
        for player, deck in enumerate(self.decks):
            physical = []
            for index, code in enumerate(deck["main"]):
                uid = f"p{player}:c{index}"
                state["cards"][uid] = {"code": code, "owner": player}
                physical.append(uid)
            chosen = next(uid for uid in physical if state["cards"][uid]["code"] == deck["chosen_champion"])
            physical.remove(chosen)
            rng.shuffle(physical)
            runes = [{"id": f"p{player}:r{i}", "code": code, "exhausted": False}
                     for i, code in enumerate(deck["runes"])]
            rng.shuffle(runes)
            state["players"].append({"main": physical[4:], "hand": physical[:4], "champion": [chosen],
                                     "gear": [], "hidden": [], "trash": [], "banishment": [], "rune_deck": runes, "runes": [], "energy": 0,
                                     "power": [], "buff_bonus": 0, "legend": deck["legend"], "legend_exhausted": False,
                                     "turns": 0, "played": 0, "finalized_played": 0,
                                     "finalized_cards": [], "ready_play": False,
                                     "free_hide_turn": False,
                                     "discarded_this_turn": False, "spell_bonus_damage": 0,
                                     "cards_locked_turn": False, "spell_discount": 0})
            state["fields"].append({"code": rng.choice(deck["battlefields"]), "controller": None})
        state["fields"].extend({"code": code, "controller": None} for code in self.extra_fields)
        state["dreaming_tree_used"] = [False] * len(state["fields"])
        state["victory"] = 8 + sum(f["code"] == "OGN-276" for f in state["fields"])
        return state

    def player(self, state):
        return state["actor"]

    def _is_field(self, state, location):
        return type(location) is int and 0 <= location < len(state["fields"])

    def _cards_locked(self, state, player):
        """Brynhir Thundersong prevents that player from playing cards this turn."""
        return bool(state["players"][player].get("cards_locked_turn"))

    def _warden_active(self, state, player):
        """Return whether an opposing Mageseeker Warden limits this player."""
        return any(unit["owner"] != player and unit["code"] == "OGN-070"
                   and self._is_field(state, unit["location"])
                   for unit in state["units"])

    def outcome(self, state):
        if state["winner"] is None:
            return None
        return (1.0, -1.0) if state["winner"] == 0 else (-1.0, 1.0)

    def _object(self, state):
        state["next_object"] += 1
        return f"u{state['next_object']}"

    def _units(self, state, player=None, location=None):
        return [u for u in state["units"] if (player is None or u["owner"] == player)
                and (location is None or u["location"] == location)]

    def _unit(self, state, uid):
        return next((u for u in state["units"] if u["id"] == uid), None)

    def _role(self, state, unit):
        battle = state["battle"]
        if battle and battle["combat"] and unit["location"] == battle["field"]:
            return "attacker" if unit["owner"] == battle["attacker"] else "defender"
        return None

    def might(self, state, unit):
        value = self.cards[unit["code"]]["might"] + unit["buff"] + unit["temporary"]
        implementation = self._card_implementation(unit["code"])
        location = unit["location"]
        if (implementation and implementation.might_effect == "plus_one_if_another_friendly_here"
                and any(other["id"] != unit["id"] and other["owner"] == unit["owner"]
                        and other["location"] == unit["location"]
                        for other in state["units"])):
            value += 1
        if (implementation is None or implementation.global_effect != "plus_one_friendly_here"):
            if (self._is_field(state, location)
                    and any(
                        other["id"] != unit["id"] and other["owner"] == unit["owner"]
                        and other["location"] == location
                        and (self._card_implementation(other["code"]) is not None)
                        and self._card_implementation(other["code"]).global_effect == "plus_one_friendly_here"
                        for other in state["units"])):
                value += 1
        if ("Mech" in self.cards.get(unit["code"], {}).get("tags", [])
                and any(
                    other["owner"] == unit["owner"]
                    and (self._card_implementation(other["code"]) is not None)
                    and self._card_implementation(other["code"]).global_effect == "mechs_plus_one"
                    for other in state["units"])):
            value += 1
        if unit["code"] == "OGN-028":
            value += state["points"][unit["owner"]]
        if unit["code"] == "OGN-109":
            value += len(state["players"][unit["owner"]]["trash"])
        if self._is_field(state, location) and state["fields"][location]["code"] == "OGN-294":
            value += 1
        role = self._role(state, unit)
        if role == "defender" and self._has_static_keyword(unit["code"], "shield_5"):
            value += 5
        if unit["code"] == "OGN-065" and unit["buff"]:
            value += 1
        if role in {"attacker", "defender"} and unit["code"] == "OGN-055":
            if len(self._units(state, unit["owner"], location)) == 1:
                value += 2
        if role == "defender" and unit["code"] == "OGN-052":
            value += 1
        if role == "defender" and unit["code"] in {"OGN-054", "OGN-074", "OGN-078", "OGN-086"}:
            value += 1
        if role == "defender" and unit["code"] == "OGN-238":
            value += 1
        if role == "defender" and unit["code"] == "OGN-241":
            value += 2
        value += unit.get("combat_shield", 0) if role == "defender" else 0
        if (self._is_field(state, location) and unit["buff"]
                and unit["code"] != "OGN-151"
                and any(other["owner"] == unit["owner"] and other["code"] == "OGN-151"
                        for other in self._units(state, location=location))):
            value += 2
        if (self._is_field(state, location) and unit["code"] == "OGN-240"):
            value += sum(other["owner"] == unit["owner"] and other["buff"]
                         for other in self._units(state, location=location))
        if (self._is_field(state, location) and unit["code"] != "OGN-243"
                and any(other["owner"] == unit["owner"] and other["code"] == "OGN-243"
                        and other["id"] != unit["id"] for other in self._units(state, location=location))):
            value += 1
        if role == "attacker":
            value += int(unit["code"] in {"OGN-210", "OGN-215"}) + unit["assault"]
            if implementation and implementation.might_effect == "assault_by_enemy":
                value += len(self._units(state, 1 - unit["owner"], location))
            value += 2 if unit["code"] == "OGN-037" else 0
            value += 3 if unit["code"] == "OGN-035" else 0
            value += 2 if unit["code"] in {"OGN-003", "OGN-030"} else 0
            value += 1 if unit["code"] == "OGN-019" and state["players"][unit["owner"]].get("discarded_this_turn") else 0
            if unit["code"] == "OGN-131" and any(not other["exhausted"]
                                                    for other in self._units(state, 1-unit["owner"], location)):
                value += 2
            value += sum(other["code"] == "OGN-015" and other["id"] != unit["id"]
                         for other in self._units(state, unit["owner"], location))
        if role == "defender" and self._is_field(state, location) and any(
                other["owner"] == unit["owner"] and other["code"] == "OGN-074"
                and other["id"] != unit["id"] for other in self._units(state, location=location)):
            value += 1
        if (unit.get("stunned") and self._is_field(state, location)
                and any(other["owner"] != unit["owner"] and other["code"] == "OGN-079"
                        for other in self._units(state, location=location))):
            value -= 8
        if role == "defender" and unit["code"] == "OGN-232" and value >= 5:
            value += 1
        if (implementation and implementation.might_effect == "double_one_on_one"
                and role in {"attacker", "defender"} and self._is_field(state, location)):
            friendly = self._units(state, unit["owner"], location)
            enemy = self._units(state, 1 - unit["owner"], location)
            if len(friendly) == 1 and len(enemy) == 1:
                value *= 2
        legend = self.card_registry.get(state["players"][unit["owner"]].get("legend"))
        if (role == "defender" and legend is not None
                and legend.global_effect == "mechs_shield"
                and "Mech" in self.cards.get(unit["code"], {}).get("tags", [])):
            value += 1
        return max(1, value)

    def _apply_buff(self, state, unit):
        """Apply the ordinary +1 buff, including Stand United's modifier."""
        if unit is None or unit["buff"]:
            return
        unit["buff"] = 1
        bonus = state["players"][unit["owner"]].get("buff_bonus", 0)
        if bonus:
            unit["temporary"] += bonus
        implementation = self._card_implementation(unit["code"])
        if implementation and implementation.buff_effect == "ready_self":
            self._ready_unit(state, unit)
        # Mistfall's E is an optional response to a friendly unit being buffed.
        # Native Mistfall and each eligible copied source use the same
        # registry-driven optional window.
        owner = unit["owner"]
        row = state["players"][owner]
        if any(power == "body" or power == "any" for power in row["power"]):
            for source in self._registry_event_sources_for_event(
                    state, owner, "friendly_unit_buffed"):
                self._queue_optional(state, owner, "mistfall_ready",
                                     source=source["id"], copied=source["copied"],
                                     target=unit["id"],
                                     registry_ability=source["ability_id"],
                                     registry_source_kind=source["kind"],
                                     registry_event=source.get("event"),
                                     registry_target_spec=source.get("target_spec"),
                                     registry_continuation=source.get("continuation"),
                                     registry_replacement_priority=source.get("replacement_priority"),
                                     registry_copy_policy=source.get("copy_policy"),
                                     event_group=source["ability_id"])

    def _radiant_stun_trigger(self, state, player):
        if state["players"][player]["legend"] != "OGN-261":
            return
        friendly = self._units(state, player)
        if friendly:
            self._apply_buff(state, friendly[0])

    def _stun_triggers(self, state, player):
        for source in self._units(state, player):
            if source["code"] == "OGN-059":
                self._ready_unit(state, source)
                source["temporary"] += 1

    def _channel_rune(self, state, player, *, exhausted=False):
        row = state["players"][player]
        if not row["rune_deck"]:
            return False
        rune = {**row["rune_deck"].pop(0), "exhausted": exhausted}
        row["runes"].append(rune)
        return True

    def _deal_damage(self, state, unit, amount):
        """Apply spell/ability damage, including Void Gate's bonus damage."""
        if unit is None:
            return
        if amount <= 0:
            return
        if unit.get("prevent_next_damage", 0):
            unit["prevent_next_damage"] = 0
            return
        if state.get("prevent_spell_ability_damage"):
            return
        if unit.get("code") == "OGN-189" and unit.get("move_count", 0) >= 2:
            return
        if self._is_field(state, unit["location"]) and state["fields"][unit["location"]]["code"] == "OGN-296":
            amount += 1
        unit["damage"] += amount
        # Imperial Decree (OGN-221) makes any unit that takes damage this
        # turn die immediately.  Mark the unit lethal here; the normal cleanup
        # path performs death processing and deathknell triggers in one place.
        decree = state.get("imperial_decree")
        if decree and decree.get("turn") == state.get("turn"):
            unit["damage"] = max(unit["damage"], self.might(state, unit))
        if unit.get("kill_on_damage") == state.get("turn"):
            unit["damage"] = max(unit["damage"], self.might(state, unit))

    def _deflect(self, state, unit):
        # Spirit's Refuge grants the same dynamic Deflect keyword to every
        # friendly buffed unit while the Gear remains in play.  Keep this in
        # the single Deflect predicate so ordinary and free-play target
        # payment paths cannot diverge.
        refuge = (unit.get("buff", 0) > 0 and any(
            gear["code"] == "OGN-063"
            for gear in state["players"][unit["owner"]]["gear"]))
        mech_aura = (
            "Mech" in self.cards.get(unit["code"], {}).get("tags", [])
            and any(
                other["owner"] == unit["owner"]
                and (self._card_implementation(other["code"]) is not None)
                and self._card_implementation(other["code"]).global_effect == "mechs_deflect_ganking"
                for other in state["units"]
            )
        )
        monument = any(
            gear["code"] == "SFD-104-221"
            for gear in state["players"][unit["owner"]].get("gear", [])
        )
        return int(unit["code"] in {"OGN-013", "OGN-041", "OGN-155", "OGN-161", "OGN-231"}
                   or self._has_static_keyword(unit["code"], "deflect")
                   or mech_aura
                   or (unit["code"] == "OGN-232" and self.might(state, unit) >= 5)
                   or refuge
                   or monument)

    def _ready_unit(self, state, unit):
        """Make a unit ready and apply ready-triggered Gear effects.

        All effect paths that ready a unit call this helper, so Pirate's
        Haven and future ready listeners cannot diverge between normal,
        copied, and replacement resolutions.  Beginning-of-turn readiness
        intentionally remains a direct state reset and does not trigger Gear.
        """
        if unit is None:
            return False
        was_exhausted = bool(unit.get("exhausted"))
        unit["exhausted"] = False
        if not was_exhausted:
            return False
        owner = unit.get("owner")
        if owner in (0, 1):
            bonus = sum(1 for gear in state["players"][owner]["gear"]
                        if gear["code"] == "OGN-143")
            if bonus:
                unit["temporary"] += bonus
        return True

    def _ganking(self, state, unit):
        location = unit["location"]
        mech_aura = (
            "Mech" in self.cards.get(unit["code"], {}).get("tags", [])
            and any(
                other["owner"] == unit["owner"]
                and (self._card_implementation(other["code"]) is not None)
                and self._card_implementation(other["code"]).global_effect == "mechs_deflect_ganking"
                for other in state["units"]
            )
        )
        return ((unit["code"] in {"OGN-112", "OGN-162", "OGN-194"})
                or self._has_static_keyword(unit["code"], "ganking")
                or mech_aura
                or (unit["code"] == "OGN-125" and unit["buff"])
                or (unit["code"] == "OGN-232" and self.might(state, unit) >= 5)
                or unit.get("temporary_ganking", False)
                or (unit["code"] == "OGN-019" and state["players"][unit["owner"]].get("discarded_this_turn"))
                or (unit["code"] in {"OGN-150", "OGN-231"})
                or (self._is_field(state, location) and state["fields"][location]["code"] == "OGN-297"))

    def _tank(self, unit):
        return (unit["code"] in {"OGN-054", "OGN-067", "OGN-087", "OGN-137", "OGN-241"}
                or self._has_static_keyword(unit["code"], "tank")
                or unit.get("temporary_tank", False))

    def _cleanup(self, state, rng=None):
        for player in (0, 1):
            if state["points"][player] >= state["victory"] and state["points"][player] > state["points"][1-player]:
                state["winner"] = player
                return
        deathknell = []
        deathknell_channel = []
        deathknell_channel_two = []
        deathknell_recycle = []
        deathknell_undercover = []
        registry_deathknell_draw = []
        registry_deathknell_draw_two = []
        registry_deathknell_gold = []
        registry_deathknell_mech = []
        wraith_draw = []
        vanguard_triggers = []
        kogmaw_fields = []
        viktor_tokens = []
        machine_tokens = []
        while True:
            dead = [u for u in state["units"] if u["damage"] > 0 and u["damage"] >= self.might(state, u)]
            if not dead:
                break
            # Replacement effects are checked before a lethal unit leaves the
            # board. Offer every applicable optional replacement first, then
            # use Zhonya as the mandatory fallback. The pending record keeps
            # this choice stable across the optional decision window.
            replaced = False
            for unit in list(dead):
                owner = unit["owner"]
                pending = state.get("death_pending")
                if pending is not None and pending.get("unit") != unit["id"]:
                    continue
                if pending is not None:
                    pending_ids = set(pending.get("option_ids", []))
                    if any(item.get("id") in pending_ids for item in state.get("optional", [])):
                        return
                    zhonya = next((g for g in state["players"][owner]["gear"]
                                   if g["id"] == pending.get("zhonya")
                                   and g["code"] == "OGN-077" and not g["exhausted"]), None)
                    if zhonya is not None:
                        state["players"][owner]["gear"].remove(zhonya)
                        self._trash_gear_card(state, zhonya)
                        unit.pop("death_replacement", None)
                        state.pop("death_pending", None)
                        unit["damage"] = 0
                        unit["location"] = f"base:{owner}"
                        unit["exhausted"] = True
                        replaced = True
                        continue
                    unit.pop("death_replacement", None)
                    state.pop("death_pending", None)
                zhonya = next((g for g in state["players"][owner]["gear"]
                               if g["code"] == "OGN-077" and not g["exhausted"]), None)
                optional_specs = []
                marker = unit.get("death_replacement") or {}
                row = state["players"][owner]
                if marker.get("kind") == "armory" and "fury" in row["power"]:
                    optional_specs.append({"effect": "armory_save", "target": unit["id"]})
                if (unit.get("buff") and any(power in DOMAINS or power == "any"
                                              for power in row["power"])):
                    for source in self._registry_event_sources_for_event(
                            state, owner, "friendly_unit_would_die", timing="replacement"):
                        if source.get("continuation") != "boss_save":
                            continue
                        optional_specs.append({
                            "effect": "boss_save", "target": unit["id"],
                            "source": source["id"], "copied": source["copied"],
                            "registry_ability": source.get("ability_id"),
                            "registry_source_kind": source.get("kind"),
                            "registry_event": source.get("event"),
                            "registry_target_spec": source.get("target_spec"),
                            "registry_continuation": source.get("continuation"),
                            "registry_replacement_priority": source.get("replacement_priority"),
                            "registry_copy_policy": source.get("copy_policy"),
                            "event_group": source.get("ability_id"),
                        })
                if optional_specs:
                    state["death_pending"] = {
                        "unit": unit["id"],
                        "zhonya": zhonya["id"] if zhonya else None,
                        "option_ids": [],
                    }
                    for spec in optional_specs:
                        effect = spec.pop("effect")
                        self._queue_optional(state, owner, effect, **spec)
                        state["death_pending"]["option_ids"].append(state["optional"][-1]["id"])
                    return
                if zhonya is not None:
                    state["players"][owner]["gear"].remove(zhonya)
                    self._trash_gear_card(state, zhonya)
                    unit.pop("death_replacement", None)
                    unit["damage"] = 0
                    unit["location"] = f"base:{owner}"
                    unit["exhausted"] = True
                    replaced = True
            if replaced:
                continue
            dead_ids = {u["id"] for u in dead}
            for unit in dead:
                was_mighty = self.might(state, unit) >= 5
                if unit.get("buff", 0):
                    for gear in state["players"][unit["owner"]]["gear"]:
                        if gear["code"] == "OGN-228":
                            candidates = [other for other in self._units(state, unit["owner"])
                                          if other["id"] != unit["id"] and other["id"] not in dead_ids]
                            if candidates:
                                vanguard_triggers.append({"effect": "vanguard_helm",
                                                          "owner": unit["owner"],
                                                          "gear": gear["id"]})
                state["units"].remove(unit)
                if unit["card"] is not None:
                    owner_row = state["players"][unit.get("card_owner", unit["owner"])]
                    owner_row["trash"].append(unit["card"])
                if unit.get("stunned"):
                    for player in (0, 1):
                        if player != unit["owner"]:
                            shrine_sources = self._registry_event_sources_for_event(
                                state, player, "stunned_enemy_destroyed")
                            shrine_sources = [source for source in shrine_sources
                                              if source.get("continuation") == "solari_shrine_draw"]
                            for shrine in shrine_sources:
                                self._queue_optional(
                                    state, player, "solari_shrine_draw",
                                    source=shrine["id"], copied=shrine["copied"],
                                    registry_ability=shrine["ability_id"],
                                    registry_source_kind=shrine["kind"],
                                    registry_event=shrine.get("event"),
                                    registry_target_spec=shrine.get("target_spec"),
                                    registry_continuation=shrine.get("continuation"),
                                    registry_replacement_priority=shrine.get("replacement_priority"),
                                    registry_copy_policy=shrine.get("copy_policy"),
                                    event_group=shrine["ability_id"])
                            if shrine_sources:
                                return
                # Karthus doubles Deathknell effects controlled by its owner
                # while it is present for the simultaneous-death check.
                multiplier = 2 if any(other["owner"] == unit["owner"]
                                      and other["code"] == "OGN-236"
                                      for other in state["units"]) else 1
                if unit["code"] == "OGN-096":
                    deathknell.extend([unit["owner"]] * multiplier)
                if unit["code"] == "OGN-216":
                    deathknell_channel.extend([unit["owner"]] * multiplier)
                if unit["code"] == "OGN-075":
                    deathknell_channel_two.extend([unit["owner"]] * multiplier)
                if unit["code"] == "OGN-110" and unit.get("card") is not None:
                    deathknell_recycle.append((self._unit_card_owner(state, unit), unit["card"]))
                if unit["code"] == "OGN-178":
                    deathknell_undercover.append(unit["owner"])
                implementation = self._card_implementation(unit["code"])
                if implementation and implementation.deathknell_effect == "draw_if_alone":
                    alone = not any(
                        other["id"] != unit["id"]
                        and other["owner"] == unit["owner"]
                        and other["location"] == unit["location"]
                        for other in state["units"]
                    )
                    if alone:
                        registry_deathknell_draw.append(unit["owner"])
                if implementation and implementation.deathknell_effect == "play_gold_gear":
                    registry_deathknell_gold.append(unit["owner"])
                if implementation and implementation.deathknell_effect == "draw_two_if_mighty" and was_mighty:
                    registry_deathknell_draw_two.append(unit["owner"])
                if implementation and implementation.deathknell_effect == "play_two_mech":
                    registry_deathknell_mech.extend([unit["owner"], unit["owner"]])
                # Each Wraith source triggers once per turn when a friendly
                # unit dies. Mark the surviving source itself so multiple
                # Wraiths each trigger once, while recursive cleanup cannot
                # trigger the same source again.
                for watcher in state["units"]:
                    if (watcher["owner"] == unit["owner"]
                            and watcher["code"] == "OGN-118"
                            and watcher["id"] not in dead_ids
                            and watcher.get("wraith_draw_turn") != state["turn"]):
                        watcher["wraith_draw_turn"] = state["turn"]
                        wraith_draw.append(watcher["owner"])
                if unit["code"] == "OGN-190" and self._is_field(state, unit["location"]):
                    kogmaw_fields.append(unit["location"])
                if unit["code"] != TOKEN and any(other["owner"] == unit["owner"]
                                                  and other["code"] == "OGN-246"
                                                  and other["id"] not in dead_ids
                                                  for other in state["units"]):
                    viktor_tokens.append(unit["owner"])
                if unit["code"] == "OGN-239":
                    machine_tokens.append(unit["owner"])
        if deathknell:
            draw_rng = rng if rng is not None else random.Random(0)
            for player in deathknell:
                self._draw(state, player, 1, draw_rng)
        if registry_deathknell_draw:
            draw_rng = rng if rng is not None else random.Random(0)
            for player in registry_deathknell_draw:
                self._draw(state, player, 1, draw_rng)
        if registry_deathknell_draw_two:
            draw_rng = rng if rng is not None else random.Random(0)
            for player in registry_deathknell_draw_two:
                self._draw(state, player, 2, draw_rng)
        if registry_deathknell_gold:
            for player in registry_deathknell_gold:
                self._play_gold_gear_token(state, player, exhausted=True)
        if registry_deathknell_mech:
            for player in registry_deathknell_mech:
                self._new_unit(state, "SFD-T05", player, f"base:{player}")
        if wraith_draw:
            draw_rng = rng if rng is not None else random.Random(0)
            for player in wraith_draw:
                self._draw(state, player, 1, draw_rng)
        for player in deathknell_channel:
            self._channel_rune(state, player, exhausted=True)
        for player in deathknell_channel_two:
            self._channel_rune(state, player, exhausted=True)
            self._channel_rune(state, player, exhausted=True)
            self._draw(state, player, 1, rng if rng is not None else random.Random(0))
        for player, card in deathknell_recycle:
            trash = state["players"][player]["trash"]
            if card in trash:
                self._recycle_cards_to_main(state, player, [card],
                                            source="trash", rng=rng or random.Random(0))
            for rune in state["players"][player]["runes"]:
                rune["exhausted"] = False
        if deathknell_undercover:
            state.setdefault("undercover_pending", []).extend(deathknell_undercover)
            if state.get("decision") is None:
                self._begin_undercover_discard(state, rng)
        if vanguard_triggers:
            if state.get("decision") is None:
                self._triggers(state, vanguard_triggers)
            else:
                state.setdefault("deferred_triggers", []).extend(vanguard_triggers)
        for player in viktor_tokens:
            self._new_unit(state, TOKEN, player, f"base:{player}")
        for player in machine_tokens:
            for _ in range(3):
                self._new_unit(state, TOKEN, player, f"base:{player}")
        if kogmaw_fields:
            for field in kogmaw_fields:
                for unit in list(self._units(state, location=field)):
                    self._deal_damage(state, unit, 4)
            self._cleanup(state, rng)
        if state["phase"] == "main":
            for field, row in enumerate(state["fields"]):
                if row["controller"] is not None and not self._units(state, row["controller"], field):
                    row["controller"] = None
            for player, row in enumerate(state["players"]):
                kept = []
                for hidden in row.get("hidden", []):
                    if state["fields"][hidden["field"]]["controller"] == player:
                        kept.append(hidden)
                    else:
                        row["trash"].append(hidden["card"])
                row["hidden"] = kept

    def _draw(self, state, player, count, rng):
        row = state["players"][player]
        had_trash = bool(row["trash"])
        result = draw_cards(tuple(row["main"]), tuple(row["trash"]), count, player=player,
                            points=tuple(state["points"]), rng=rng, victory=state["victory"])
        row["main"], row["trash"] = list(result.main), list(result.trash)
        row["hand"].extend(result.drawn)
        state["points"] = list(result.points)
        if result.burnouts and had_trash:
            self._trigger_recycle_event(state, player)
        if result.immediate_winner is not None:
            state["winner"] = result.immediate_winner

    def _begin_undercover_discard(self, state, rng=None):
        """Open Undercover Agent's mandatory Deathknell discard window."""
        pending = state.get("undercover_pending", [])
        if not pending or state.get("decision") is not None:
            return
        player = pending.pop(0)
        row = state["players"][player]
        state["undercover_player"] = player
        if not row["hand"]:
            self._draw(state, player, 2, rng if rng is not None else random.Random(0))
            state.pop("undercover_player", None)
            if state.get("undercover_pending"):
                self._begin_undercover_discard(state, rng)
            return
        if state.get("undercover_resume") is None:
            state["undercover_resume"] = {
                "phase": state.get("phase", "main"),
                "actor": state.get("actor", player),
                "passes": state.get("passes", 0),
            }
        state["decision"] = {
            "kind": "discard", "player": player,
            "remaining": min(2, len(row["hand"])),
            "undercover_discard": True,
        }
        state["phase"], state["actor"], state["passes"] = "decision", player, 0

    def _finish_undercover_discard(self, state, rng):
        """Finish one Undercover discard and restore its Deathknell context."""
        resume = state.pop("undercover_resume", None)
        state["decision"] = None
        if resume is None:
            resume = {"phase": "main", "actor": state["turn_player"], "passes": 0}
        player = state.pop("undercover_player", resume["actor"])
        state["phase"], state["actor"], state["passes"] = (
            resume["phase"], resume["actor"], resume.get("passes", 0))
        self._draw(state, player, 2, rng)
        self._cleanup(state, rng)
        if state.get("decision") is None and state.get("undercover_pending"):
            self._begin_undercover_discard(state, rng)
        if state.get("decision") is None and state.get("deferred_triggers"):
            self._triggers(state, state.pop("deferred_triggers"))

    def _recycle_cards_to_main(self, state, player, cards, *, source, rng):
        """Move cards to the bottom of Main Deck and emit one recycle event."""
        row = state["players"][player]
        zone = row[source]
        selected = [uid for uid in cards if uid in zone]
        if not selected:
            return 0
        for uid in selected:
            zone.remove(uid)
        if len(selected) > 1:
            rng.shuffle(selected)
        row["main"].extend(selected)
        self._trigger_recycle_event(state, player)
        return len(selected)

    def _trigger_jinx_discard(self, state, player):
        """Put one mandatory Jinx trigger per discard event on the chain."""
        row = state["players"][player]
        offered = state.setdefault("flame_chompers_offered", [])
        for card in row["trash"]:
            if (self.cards[state["cards"][card]["code"]]["code"] == "OGN-006"
                    and card not in offered):
                offered.append(card)
                self._queue_optional(state, player, "play_flame_chompers", card=card)
        triggers = [{"effect": "jinx_discard", "source": unit["id"],
                     "owner": player}
                    for unit in self._units(state, player)
                    if unit["code"] == "OGN-202"]
        if not triggers:
            return
        if not state.get("chain") and "chain_return" not in state:
            state["chain_return"] = state.get("phase", "main")
            state["chain_from_spell"] = False
        state["chain"].extend(triggers)
        state["phase"], state["actor"], state["passes"] = "chain", player, 0
        self._arm_chain_top(state)

    def _trigger_recycle_event(self, state, player):
        """Emit one mandatory Karma trigger for a card recycle event."""
        triggers = [{"effect": "karma_recycle", "source": unit["id"],
                     "owner": player}
                    for unit in self._units(state, player)
                    if unit["code"] == "OGN-235"
                    or (self._card_implementation(unit["code"]) is not None
                        and self._card_implementation(unit["code"]).global_effect == "vision_recycle")]
        if not triggers:
            return
        if not state.get("chain") and "chain_return" not in state:
            state["chain_return"] = state.get("phase", "main")
            state["chain_from_spell"] = False
        state["chain"].extend(triggers)
        state["phase"], state["actor"], state["passes"] = "chain", player, 0
        self._arm_chain_top(state)

    def _queue_optional(self, state, player, effect, **payload):
        state["next_object"] += 1
        optional = state.setdefault("optional", [])
        if not optional:
            state["optional_return"] = {
                "phase": state["phase"], "actor": state["actor"],
                "passes": state.get("passes", 0),
            }
            state["optional_ordered"] = False
            state["phase"], state["actor"], state["passes"] = "optional", player, 0
        optional.append({
            "id": f"o{state['next_object']}", "player": player, "effect": effect, **payload
        })

    def _queue_battlefield_optional(self, state, player, effect, **payload):
        """Queue a battlefield may-effect after one score event completes.

        Beginning Phase scoring can inspect more than one controlled
        battlefield.  Collecting these triggers until all score events have
        been generated prevents the first field from opening a decision window
        while the remaining fields are still being evaluated.  The normal
        optional queue then applies the same ordering window (RUP5 383.3.d/e)
        to the collected abilities.
        """
        if state.get("collecting_battlefield_triggers"):
            state.setdefault("deferred_battlefield_optionals", []).append(
                {"player": player, "effect": effect, **payload})
            return
        self._queue_optional(state, player, effect, **payload)

    def _flush_deferred_battlefield_optionals(self, state):
        deferred = state.pop("deferred_battlefield_optionals", [])
        for trigger in deferred:
            trigger = dict(trigger)
            self._queue_optional(state, trigger.pop("player"),
                                 trigger.pop("effect"), **trigger)

    def _complete_death_replacement(self, state, target_id):
        """Consume a chosen death replacement and discard sibling choices."""
        pending = state.get("death_pending")
        if pending is None or pending.get("unit") != target_id:
            return
        sibling_ids = set(pending.get("option_ids", []))
        state["optional"] = [item for item in state.get("optional", [])
                              if item.get("id") not in sibling_ids]
        state.pop("death_pending", None)

    def _open_reveal(self, state, *, owner, cards, mode, chooser=None,
                     minimum=0, maximum=0, effect=None, item=None, choices=None,
                     closer=None, rng=None):
        """Open a public card reveal window.

        ``display`` waits for the revealed player's opponent (``closer``) to
        end the reveal. ``select`` keeps the revealed cards public while the
        chooser selects and confirms cards.  ``owner`` always identifies the
        player whose cards are being revealed; it is deliberately separate
        from the player who is allowed to close or select the window.
        The saved phase/actor lets the normal chain resolver continue after the
        window closes.
        """
        if closer is None:
            closer = (1 - owner) if mode == "display" else (
                chooser if chooser is not None else owner)
        state["reveal"] = {
            "kind": mode, "owner": owner, "opponent": 1 - owner,
            "chooser": chooser if chooser is not None else owner,
            "closer": closer,
            "cards": list(cards), "selected": [], "min": minimum,
            "max": maximum, "choices": list(choices) if choices is not None else list(cards),
            "effect": effect, "item": item,
            "resume": {"phase": state["phase"], "actor": state["actor"],
                       "passes": state.get("passes", 0)},
        }
        state["reveal"]["nocturne_queue"] = [uid for uid in cards
                                                if uid in state["players"][owner]["main"]
                                                and state["cards"][uid]["code"] == "OGN-194"]
        state["phase"] = "reveal"
        state["actor"] = state["reveal"]["closer"] if mode == "display" else state["reveal"]["chooser"]
        state["passes"] = 0
        self._open_next_nocturne_replacement(state)

    def _open_next_nocturne_replacement(self, state):
        """Pause a look/reveal before exposing each Nocturne to an opponent."""
        reveal = state.get("reveal")
        if not reveal or not reveal.get("nocturne_queue"):
            return False
        card = reveal["nocturne_queue"].pop(0)
        reveal["nocturne_current"] = card
        owner = reveal["owner"]
        state["decision"] = {
            "kind": "choice", "player": owner,
            "options": ["nocturne_banish", "nocturne_skip"],
            "nocturne_reveal": {"card": card, "owner": owner,
                                "aurora_stop": reveal.get("effect") == "dazzling_aurora"},
        }
        state["phase"], state["actor"], state["passes"] = "decision", owner, 0
        return True

    def _resume_reveal_after_nocturne(self, state):
        reveal = state.get("reveal")
        if reveal is None:
            return
        state["decision"] = None
        state["phase"] = "reveal"
        state["actor"] = reveal["closer"] if reveal["kind"] == "display" else reveal["chooser"]
        state["passes"] = 0
        self._open_next_nocturne_replacement(state)

    def _free_play_revealed_card(self, state, owner, card, parent, rng, *, ignore_energy=False,
                                 free_all=False, card_owner=None, energy_reduction=0):
        """Play a unit/gear/spell selected by a reveal or zone continuation.

        The card is returned to the controller's hand only for the duration of
        the ordinary play path.  It remains a physical card with its original
        identity, while units/gears receive the new controller and spell
        triggers continue through the normal Chain. ``energy_reduction`` and
        ``ignore_energy`` are replacement-cost parameters; Power payment and
        entry triggers still use the ordinary play path.
        """
        row = state["players"][owner]
        physical_row = state["players"][card_owner] if card_owner is not None else row
        code = state["cards"][card]["code"]
        data = self.cards[code]

        # Units whose play process itself needs a target use the same click
        # window as ordinary hand plays.  Triggered entry abilities such as
        # Snapvine are intentionally left to the normal post-entry Chain
        # trigger path, so their target is chosen only after the unit exists.
        unit_target = self._free_play_unit_target_spec(state, owner, code)
        if data["type"] == "unit" and unit_target is not None:
            candidates = list(unit_target.get("candidates", []))
            if candidates:
                state["decision"] = {
                    "kind": "target", "player": owner,
                    "targets": candidates, "item": parent,
                    "free_play_unit": {
                        "owner": owner, "card": card,
                        "card_owner": card_owner if card_owner is not None else owner,
                        "parent": parent, "ignore_energy": ignore_energy,
                        "free_all": free_all,
                        # Entry target selection precedes the resource window.
                        # This mirrors ordinary targeted plays and prevents a
                        # nested free play from exposing payment choices before
                        # the player has confirmed the actual target.
                        "payment": [] if free_all else None,
                        "energy_reduction": energy_reduction,
                    },
                }
                state["phase"], state["actor"], state["passes"] = "decision", owner, 0
                return

        # A revealed spell is still a normal spell play.  In particular, its
        # target choices are made by the player after the replacement effect
        # has put the card on the stack; taking the first legal target here
        # silently changes the printed effect.  Keep the physical card in its
        # current banishment/hand zone while the target window is open, then
        # move it to the controller's hand only when the player confirms.
        free_target = self._free_play_target_spec(state, owner, code)
        if (data["type"] == "spell" and free_target is not None
                and free_target.get("kind") == "field"):
            state["decision"] = {
                "kind": "field", "player": owner,
                "fields": list(free_target.get("fields", [])),
                "x_choice": bool(free_target.get("x_choice")),
                "x_max": len(row.get("power", [])),
                "free_play_field": {
                    "owner": owner, "card": card,
                    "card_owner": card_owner if card_owner is not None else owner,
                    "parent": parent,
                    # Power payment is deliberately deferred until after the
                    # battlefield is selected, matching ordinary target
                    # spells and keeping all free-play targets interactive.
                    "payment": None if ignore_energy and not free_all else [],
                    "ignore_energy": ignore_energy, "free_all": free_all,
                    "fields": list(free_target.get("fields", [])),
                    "x_choice": bool(free_target.get("x_choice")), "field": None,
                    "x": 0,
                },
            }
            state["phase"], state["actor"], state["passes"] = "decision", owner, 0
            return
        if (data["type"] == "spell" and free_target is not None
                and (free_target["candidates"] or free_target.get("min", 1) == 0)):
            # With no legal target, keep the card in the ordinary free-play
            # path with an empty target list so it can resolve/fizzle and move
            # to its normal destination.  Never substitute an arbitrary unit.
            payment = None if ignore_energy and not free_all else []
            # For a free target spell, Deflect depends on the final target
            # selection.  Compute its payment only after the target window is
            # confirmed in ``_complete_free_play_target``.
            if ignore_energy and free_all:
                payment = []
            state["decision"] = {
                "kind": "target", "player": owner,
                "targets": free_target["candidates"],
                "multi": (free_target["max"] != 1 or free_target.get("allow_repeat", False)
                          or free_target.get("min", 1) == 0),
                "min": free_target["min"], "max": free_target["max"],
                "selected": [], "allow_repeat": free_target.get("allow_repeat", False),
                "target_pairs": free_target.get("target_pairs"),
                "target_might_limit": free_target.get("target_might_limit"),
                "same_location": free_target.get("same_location", False),
                "destination_select": free_target.get("destination_select", False),
                "free_play": {"owner": owner, "card": card,
                               "card_owner": card_owner if card_owner is not None else owner,
                               "parent": parent, "payment": payment,
                               "destination": None, "ignore_energy": ignore_energy,
                               "free_all": free_all,
                               "deck_options": free_target.get("deck_options", []),
                               # Blind Fury/Promising Future already put
                               # their parent item on a live Chain; Kaisa's
                               # optional replay starts from Main. Preserve
                               # that context when the target is confirmed.
                               "resume_chain": bool(state.get("chain")) or state.get("phase") == "chain"},
            }
            state["phase"], state["actor"], state["passes"] = "decision", owner, 0
            return
        if card in physical_row.get("banishment", []):
            physical_row["banishment"].remove(card)
        if card not in row["hand"]:
            row["hand"].append(card)
        if parent is not None and parent not in state.get("chain", []) and parent.get("effect") != "kaisa_replay_spell":
            state.setdefault("chain", []).append(parent)
        if data["type"] == "unit":
            payment = []
            required_energy = 0 if ignore_energy else max(0, data["energy"] - energy_reduction)
            if ignore_energy or energy_reduction:
                choices = self._payments(state, owner, required_energy,
                                         data["domains"], data["power_cost"])
                if not choices:
                    row["hand"].remove(card)
                    row["banishment"].append(card)
                    return
                payment = [] if free_all else choices[0]
                if len(choices) > 1 and not free_all:
                    state["decision"] = {
                        "kind": "free_play_payment", "player": owner,
                        "payments": choices, "targets": [],
                        "free_play_unit": {
                            "owner": owner, "card": card,
                            "card_owner": card_owner if card_owner is not None else owner,
                            "parent": parent, "ignore_energy": ignore_energy,
                            "free_all": free_all, "payment": None,
                            "energy_reduction": energy_reduction,
                        },
                    }
                    state["phase"], state["actor"], state["passes"] = "decision", owner, 0
                    return
            self.apply(state, Action.make("play_unit", card=card,
                                          location=f"base:{owner}", accelerate=False,
                                          payment=payment, enter_target=None,
                                          ignore_cost=((not ignore_energy and not energy_reduction)
                                                       or free_all),
                                          card_owner=card_owner,
                                          ignore_energy=ignore_energy or free_all,
                                          energy_reduction=energy_reduction,
                                          free_play_parent=True), rng)
            if (parent is not None and parent in state.get("chain", [])
                    and state.get("phase") == "main"):
                state["phase"], state["actor"], state["passes"] = (
                    "chain", state["chain"][-1]["owner"], 0)
            return
        if data["type"] == "gear":
            payment = []
            if ignore_energy:
                choices = self._payments(state, owner, 0, data["domains"], data["power_cost"])
                if not choices:
                    row["hand"].remove(card)
                    row["banishment"].append(card)
                    return
                payment = [] if free_all else choices[0]
                if len(choices) > 1 and not free_all:
                    state["decision"] = {
                        "kind": "free_play_payment", "player": owner,
                        "payments": choices, "targets": [],
                        "free_play_gear": {
                            "owner": owner, "card": card,
                            "card_owner": card_owner if card_owner is not None else owner,
                            "parent": parent, "payment": None,
                            "ignore_energy": ignore_energy, "free_all": free_all,
                        },
                    }
                    state["phase"], state["actor"], state["passes"] = "decision", owner, 0
                    return
            self.apply(state, Action.make("play_gear", card=card, payment=payment,
                                          ignore_cost=(not ignore_energy or free_all),
                                          card_owner=card_owner,
                                          ignore_energy=ignore_energy or free_all), rng)
            if (parent is not None and parent in state.get("chain", [])
                    and state.get("phase") == "main"):
                state["phase"], state["actor"], state["passes"] = (
                    "chain", state["chain"][-1]["owner"], 0)
            return
        payment = []
        if ignore_energy:
            choices = self._payments(state, owner, 0, data["domains"], data["power_cost"], spell=True)
            if not choices:
                row["hand"].remove(card)
                row["banishment"].append(card)
                return
            payment = [] if free_all else choices[0]
            if len(choices) > 1 and not free_all:
                state["decision"] = {
                    "kind": "free_play_payment", "player": owner,
                    "payments": choices, "targets": [],
                    "free_play_spell": {
                        "owner": owner, "card": card,
                        "card_owner": card_owner if card_owner is not None else owner,
                        "parent": parent, "payment": None,
                        "ignore_energy": ignore_energy, "free_all": free_all,
                        "selected": [], "destination": None,
                        "deck_options": [],
                    },
                }
                state["phase"], state["actor"], state["passes"] = "decision", owner, 0
                return
        self.apply(state, Action.make("play_spell", card=card, targets=[],
                                      destination=None, spend_buff=None,
                                      payment=payment, ignore_cost=(not ignore_energy or free_all),
                                      card_owner=card_owner,
                                      ignore_energy=ignore_energy), rng)
        if parent is not None and parent.get("effect") == "kaisa_replay_spell":
            for entry in reversed(state.get("chain", [])):
                if entry.get("card") == card:
                    entry["recycle_after"] = True
                    break

    def _free_play_unit_target_spec(self, state, owner, code):
        """Return entry-target candidates for a unit played by an effect."""
        if code == "OGN-016" and self._played_for_legion(state, owner):
            return {"candidates": [u["id"] for u in self._units(state, owner)]}
        return None

    def _spell_target_spec(self, state, owner, code):
        """Return the canonical interactive target specification for a spell.

        Ordinary hand plays and replacement/free plays must use the same
        target restrictions.  Keeping this shape in one helper prevents a
        free replay from silently selecting a different target class (or
        skipping a required field/target window) than a normal play.
        """
        targeted = (SIMPLE_TARGET_SPELLS | PAIR_TARGET_SPELLS |
                    DESTINATION_TARGET_SPELLS | OPTIONAL_TARGET_SPELLS |
                    CONSTRAINED_MULTI_TARGET_SPELLS | {"OGN-029", "OGN-104",
                    "OGN-105", "OGN-183", "OGN-206", "OGN-248"})
        if code in FIELD_TARGET_SPELLS or code == "OGN-268":
            return {"kind": "field", "fields": list(range(len(state["fields"]))),
                    "x_choice": code == "OGN-268"}
        if code not in targeted:
            return None
        if code == "OGN-183":
            options = list(state["players"][owner]["main"][:3])
            return {"candidates": options, "min": 1 if options else 0,
                    "max": 1, "deck_options": options}
        if code == "OGN-104":
            candidates = [u["id"] for u in self._units(state, owner)]
            return {"candidates": candidates, "min": 1, "max": 1}
        if code == "OGN-206":
            candidates = [u["id"] for u in self._units(state, owner)]
            pairs = [[a["id"], b["id"]] for a in self._units(state, owner)
                     for b in self._units(state, owner) if a["id"] != b["id"]]
            return {"candidates": candidates, "min": 2, "max": 2,
                    "multi": True, "target_pairs": pairs}
        if code in PAIR_TARGET_SPELLS:
            pairs = []
            if code == "OGN-108":
                pairs = [[a["id"], b["id"]] for a in self._units(state, owner)
                         for b in self._units(state, owner) if a["id"] != b["id"]]
            elif code == "OGN-260":
                pairs = [[a["id"], b["id"]] for a in self._units(state, owner)
                         for b in self._units(state, 1 - owner)
                         if self._is_field(state, b["location"])]
            elif code == "OGN-220":
                pairs = [[a["id"], b["id"]]
                         for field in range(len(state["fields"]))
                         for a in self._units(state, owner, field)
                         for b in self._units(state, 1 - owner, field)]
            else:
                pairs = [[a["id"], b["id"]] for a in self._units(state, owner)
                         for b in self._units(state, 1 - owner)]
            return {"candidates": sorted({uid for pair in pairs for uid in pair}, key=str),
                    "min": 2, "max": 2, "multi": True,
                    "target_pairs": pairs}
        if code == "OGN-029":
            candidates = [u["id"] for u in state["units"]]
            return {"candidates": candidates, "min": 2,
                    "max": 2, "allow_repeat": True}
        if code == "OGN-105":
            candidates = [u["id"] for u in state["units"]]
            return {"candidates": candidates, "min": 0, "max": 2}
        if code == "OGN-248":
            candidates = [u["id"] for u in state["units"]
                          if self._is_field(state, u["location"])]
            return {"candidates": candidates, "min": 6,
                    "max": 6, "allow_repeat": True}
        if code in OPTIONAL_TARGET_SPELLS:
            candidates = [u["id"] for u in self._units(state, owner) if not u["exhausted"]]
            return {"candidates": candidates, "min": 0, "max": 1}
        if code in CONSTRAINED_MULTI_TARGET_SPELLS:
            candidates = [u["id"] for u in state["units"] if self._is_field(state, u["location"])]
            return {"candidates": candidates, "min": 0, "max": len(candidates),
                    "target_might_limit": 4, "same_location": True}
        if code == "OGN-180":
            candidates = ([u["id"] for u in state["units"] if self._is_field(state, u["location"])]
                          + [gear["id"] for row in state["players"] for gear in row["gear"]])
            return {"candidates": candidates, "min": 1, "max": 1}
        if code == "OGN-203":
            candidates = [u["id"] for u in self._units(state, 1 - owner)
                          if self._is_field(state, u["location"])]
            return {"candidates": candidates, "min": 1, "max": 1}
        if code in {"OGN-008", "OGN-057", "OGN-168"}:
            candidates = [u["id"] for u in state["units"]
                          if self._is_field(state, u["location"])]
            return {"candidates": candidates, "min": 1, "max": 1}
        if code in {"OGN-033"}:
            candidates = [u["id"] for u in self._units(state, 1 - owner)]
            return {"candidates": candidates, "min": 1, "max": 1}
        if code in {"OGN-046", "OGN-053", "OGN-069", "OGN-102", "OGN-146", "OGN-207"}:
            candidates = [u["id"] for u in self._units(state, owner)]
            return {"candidates": candidates, "min": 1, "max": 1}
        if code == "OGN-262":
            candidates = [u["id"] for u in self._units(state, 1 - owner)
                          if self._is_field(state, u["location"])]
            return {"candidates": candidates, "min": 1, "max": 1}
        if code in {"OGN-169", "OGN-172", "OGN-213"}:
            candidates = [u["id"] for u in state["units"]
                          if self._is_field(state, u["location"])
                          and (code != "OGN-169" or self.might(state, u) <= 3)]
            return {"candidates": candidates, "min": 1, "max": 1}
        if code in DESTINATION_TARGET_SPELLS:
            candidates = []
            for unit in state["units"]:
                if code == "OGN-043" and unit["owner"] == owner:
                    continue
                if code == "OGN-173" and unit["owner"] != owner:
                    continue
                if code in {"OGN-250", "OGN-270"} and (unit["owner"] != owner or
                                                        unit["location"] != f"base:{owner}"):
                    continue
                if code == "OGN-258" and unit["owner"] == owner:
                    continue
                candidates.append(unit["id"])
            return {"candidates": candidates, "min": 1,
                    "max": 1, "destination_select": True}
        candidates = [u["id"] for u in state["units"]
                      if code not in {"OGN-005", "OGN-009", "OGN-014", "OGN-024", "OGN-085"}
                      or self._is_field(state, u["location"])]
        return {"candidates": candidates, "min": 1, "max": 1}

    # Kept as a compatibility alias for callers and older replay fixtures.
    def _free_play_target_spec(self, state, owner, code):
        return self._spell_target_spec(state, owner, code)

    def _finish_reveal(self, state, selected, rng):
        reveal = state.get("reveal")
        if reveal is None:
            raise ValueError("no reveal window is active")
        effect = reveal.get("effect")
        if effect == "draw_one_recycle_one":
            owner = reveal["owner"]
            row = state["players"][owner]
            original = [uid for uid in reveal.get("cards", []) if uid in row["main"]]
            chosen = selected[0] if selected else None
            if chosen is not None and chosen in row["main"]:
                row["main"].remove(chosen)
                row["hand"].append(chosen)
            remaining = [uid for uid in original if uid != chosen and uid in row["main"]]
            if remaining:
                self._recycle_cards_to_main(state, owner, remaining, source="main", rng=rng)
            item = reveal.get("item")
            state["reveal"] = None
            if item is not None:
                item["reveal_done"] = True
                state["chain"].append(item)
                state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                self._finish_resolution(state)
            return
        if effect == "apprentice_smith":
            owner = reveal["owner"]
            row = state["players"][owner]
            card = next((uid for uid in reveal.get("cards", []) if uid in row["main"]), None)
            item = reveal.get("item")
            if card is not None:
                if self.cards[state["cards"][card]["code"]]["type"] == "gear":
                    row["main"].remove(card)
                    row["hand"].append(card)
                else:
                    self._recycle_cards_to_main(state, owner, [card], source="main", rng=rng)
            state["reveal"] = None
            if item is not None:
                item["reveal_done"] = True
                state["chain"].append(item)
                state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                self._finish_resolution(state)
            return
        if effect == "dazzling_aurora":
            owner = reveal["owner"]
            row = state["players"][owner]
            card = next((uid for uid in reveal.get("cards", [])
                         if uid in row["main"]), None)
            continuation = reveal.get("item") or {
                "effect": "dazzling_aurora_continue", "owner": owner,
            }
            # The reveal window is complete, but the continuation remains on
            # the Chain so every recycle trigger and every ordinary free-play
            # trigger resolves before Aurora looks at its next card.
            state["reveal"] = None
            if not state.get("chain") and "chain_return" not in state:
                state["chain_return"] = "main"
                state["chain_from_spell"] = False
            state["chain"].append(continuation)
            if card is not None and self.cards[state["cards"][card]["code"]]["type"] == "unit":
                continuation["advance_gear"] = True
                row["main"].remove(card)
                row["banishment"].append(card)
                state["phase"], state["actor"], state["passes"] = "chain", owner, 0
                self._free_play_revealed_card(
                    state, owner, card, continuation, rng,
                    free_all=True, card_owner=owner)
                return
            if card is not None:
                # Keep the card in Main until the generic recycle operation
                # moves it to the bottom and emits Karma's recycle event.
                self._recycle_cards_to_main(state, owner, [card], source="main", rng=rng)
            if state.get("phase") != "chain":
                state["phase"], state["actor"], state["passes"] = "chain", owner, 0
            self._finish_resolution(state)
            self._cleanup(state, rng)
            return
        if effect == "blind_fury":
            owner = reveal["owner"]
            chosen = selected[0] if selected else None
            remaining = [uid for uid in reveal["cards"] if uid != chosen]
            self._recycle_cards_to_main(state, owner, remaining, source="main", rng=rng)
            item = reveal.get("item")
            if item is not None and chosen is not None:
                row = state["players"][owner]
                if chosen in row["main"]:
                    row["main"].remove(chosen)
                # The caster gains control of the play, but the physical card
                # remains owned by the player whose Main Deck was revealed.
                # Keep it in that player's Banishment zone until the ordinary
                # play path consumes it.
                state["players"][owner]["banishment"].append(chosen)
                item["reveal_done"] = True
                state["chain"].append(item)
                state["reveal"] = None
                state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                # Blind Fury explicitly says to play the revealed card while
                # ignoring its cost (Energy and Power).  Preserve the normal
                # target/entry windows, but mark this replacement as a full
                # cost waiver rather than the Promising Future-style
                # Energy-only waiver.
                self._free_play_revealed_card(state, item["owner"], chosen, item, rng,
                                              free_all=True, card_owner=owner)
                return
        if effect == "promising_future":
            owner = reveal["owner"]
            chosen = selected[0] if selected else None
            remaining = [uid for uid in reveal["cards"] if uid != chosen]
            self._recycle_cards_to_main(state, owner, remaining, source="main", rng=rng)
            item = reveal.get("item")
            if item is not None:
                if chosen is not None:
                    row = state["players"][owner]
                    if chosen in row["main"]:
                        row["main"].remove(chosen)
                    row["banishment"].append(chosen)
                item.setdefault("future_cards", {})[owner] = chosen
                next_owner = next((p for p in (0, 1) if p not in item["future_cards"]), None)
                if next_owner is not None:
                    top = list(state["players"][next_owner]["main"][:5])
                    self._open_reveal(state, owner=next_owner, cards=top, mode="select",
                                      chooser=next_owner, minimum=1 if top else 0, maximum=1,
                                      effect="promising_future", item=item, choices=top, rng=rng)
                    return
                item["reveal_done"] = True
                item["future_queue"] = [p for p in (1 - item["owner"], item["owner"])
                                        if item["future_cards"].get(p) is not None]
                state["chain"].append(item)
                state["reveal"] = None
                state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                if item["future_queue"]:
                    play_owner = item["future_queue"].pop(0)
                    card = item["future_cards"][play_owner]
                    row = state["players"][play_owner]
                    if card in row["banishment"]:
                        row["banishment"].remove(card)
                    row["hand"].append(card)
                    state["actor"] = play_owner
                    self._free_play_revealed_card(state, play_owner, card, item, rng,
                                                  ignore_energy=True)
                else:
                    item["future_complete"] = True
                return
        if effect == "reinforce":
            owner = reveal["owner"]
            row = state["players"][owner]
            selected_set = set(selected)
            remaining = [uid for uid in reveal["cards"] if uid not in selected_set]
            item = reveal.get("item")
            if item is not None:
                item["reveal_done"] = True
                # Recycle only when the Reinforce continuation resolves. This
                # preserves the printed order and lets Karma's recycle trigger
                # enter the normal Chain instead of being overwritten by the
                # unit-payment/target window.
                item["reinforce_remaining"] = remaining
                state["reveal"] = None
                state["chain"].append(item)
            if selected:
                card = selected[0]
                if card in row["main"]:
                    row["main"].remove(card)
                row["banishment"].append(card)
                if self.cards[state["cards"][card]["code"]]["type"] == "unit":
                    if item is not None:
                        state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    self._free_play_revealed_card(
                        state, owner, card, item, rng,
                        card_owner=owner, energy_reduction=5)
                    return
            if item is not None:
                state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                self._finish_resolution(state)
                self._cleanup(state, rng)
            return
        elif effect == "kaisa_replay_spell":
            owner = reveal["owner"]
            row = state["players"][owner]
            chosen = selected[0] if selected else None
            item = reveal.get("item")
            if chosen is not None and chosen in row["trash"]:
                row["trash"].remove(chosen)
                row["hand"].append(chosen)
                state["reveal"] = None
                state["phase"], state["actor"], state["passes"] = "main", owner, 0
                self._free_play_revealed_card(state, owner, chosen, item or {
                    "effect": "kaisa_replay_spell", "owner": owner}, rng,
                    ignore_energy=True)
                if chosen in row["trash"]:
                    self._recycle_cards_to_main(state, owner, [chosen], source="trash", rng=rng)
                # The free-play helper may leave an explicit target decision
                # open.  Do not let the reveal finalizer below overwrite that
                # decision's phase; the normal spell chain will resume after
                # the target is confirmed.
                return
        elif effect == "sabotage_recycle":
            self._recycle_cards_to_main(state, reveal["owner"], selected,
                                        source="hand", rng=rng)
            item = reveal.get("item")
            if item is not None:
                item["reveal_done"] = True
                state["chain"].append(item)
        elif effect == "mindsplitter":
            # The selected card belongs to the revealed opponent.  Move the
            # physical card to that player's trash, then return the original
            # triggered item to the Chain for normal continuation cleanup.
            revealed_owner = reveal["owner"]
            row = state["players"][revealed_owner]
            chosen = selected[0] if selected else None
            if chosen is not None and chosen in row["hand"]:
                row["hand"].remove(chosen)
                row["trash"].append(chosen)
                row["discarded_this_turn"] = True
                self._trigger_jinx_discard(state, revealed_owner)
            item = reveal.get("item")
            if item is not None:
                item["reveal_done"] = True
                state["chain"].append(item)
        elif effect == "dr_mundo_recycle":
            self._recycle_cards_to_main(state, reveal["owner"], selected,
                                        source="trash", rng=rng)
        elif effect == "recycle_top_two":
            # Candlelit Sanctum lets its controller recycle zero, one, or both
            # cards and then put every card that was not recycled back in any
            # order.  The ordinary reveal window is therefore followed by a
            # small explicit permutation window when two cards remain.
            owner = reveal["owner"]
            if reveal.get("kind") == "reorder" or reveal.get("ordered"):
                # During the second window ``selected`` is the retained-card
                # order, while ``recycle_selected`` is the first-window
                # choice.  The order action currently normalizes the window
                # back to ``kind=select`` before calling this finalizer, so
                # check both markers.
                recycled = list(reveal.get("recycle_selected", []))
                ordered = list(reveal.get("ordered_cards", selected))
                self._recycle_cards_to_main(state, owner, recycled,
                                            source="main", rng=rng)
                row = state["players"][owner]
                ordered_set = set(ordered)
                row["main"] = ordered + [uid for uid in row["main"]
                                          if uid not in ordered_set]
            else:
                original = list(reveal.get("original_cards", reveal["cards"]))
                recycled = list(selected)
                remaining = [uid for uid in original if uid not in set(recycled)]
                if len(remaining) > 1:
                    reveal["kind"] = "reorder"
                    reveal["original_cards"] = original
                    reveal["recycle_selected"] = recycled
                    reveal["cards"] = list(remaining)
                    reveal["choices"] = list(remaining)
                    reveal["selected"] = []
                    reveal["min"] = reveal["max"] = len(remaining)
                    state["phase"] = "reveal"
                    state["actor"] = reveal["chooser"]
                    state["passes"] = 0
                    return
                # With zero or one retained cards there is no ordering window.
                self._recycle_cards_to_main(state, owner, recycled,
                                            source="main", rng=rng)
        elif effect == "forge_recycle":
            for owner in (0, 1):
                cards = [uid for uid in selected if uid in state["players"][owner]["trash"]]
                self._recycle_cards_to_main(state, owner, cards, source="trash", rng=rng)
        elif effect == "baited_hook":
            # Baited Hook reveals the top five, lets the controller banish at
            # most one eligible unit, and recycles every other revealed card.
            # The selected unit is played for free at the controller's Base;
            # its entry trigger is intentionally handled by the ordinary
            # unit path when a future card-play continuation is available.
            owner = reveal["owner"]
            row = state["players"][owner]
            cards = [uid for uid in reveal["cards"] if uid in row["main"]]
            chosen = selected[0] if selected else None
            if chosen is not None and chosen in cards:
                cards.remove(chosen)
                row["main"].remove(chosen)
                row["banishment"].append(chosen)
                # Keep the remaining cards in a continuation item so the
                # selected unit is played through the ordinary play path
                # (including entry targets/triggers) before recycling occurs.
                continuation = {"effect": "baited_hook_finish", "owner": owner,
                                "remaining": cards}
                state["reveal"] = None
                state["chain"].append(continuation)
                state["phase"], state["actor"], state["passes"] = "chain", owner, 0
                self._free_play_revealed_card(state, owner, chosen, continuation, rng,
                                              free_all=True, card_owner=owner)
                return
            self._recycle_cards_to_main(state, owner, cards, source="main", rng=rng)
        elif effect == "harrowing_play":
            owner = reveal["owner"]
            row = state["players"][owner]
            card = selected[0] if selected else None
            item = reveal.get("item")
            state["reveal"] = None
            continuation = {
                "effect": "harrowing_finish", "owner": owner,
                "card": item.get("card") if item else None,
                "code": "OGN-198",
                "played_by": item.get("played_by", owner) if item else owner,
                "post_triggers": list(item.get("post_triggers", [])) if item else [],
            }
            state["chain"].append(continuation)
            state["phase"], state["actor"], state["passes"] = "chain", owner, 0
            if card is None or card not in row["trash"]:
                return
            data = self.cards[state["cards"][card]["code"]]
            payments = self._payments(state, owner, 0, data["domains"], data["power_cost"])
            if not payments:
                return
            row["trash"].remove(card)
            row["hand"].append(card)
            self._free_play_revealed_card(
                state, owner, card, continuation, rng,
                ignore_energy=True, card_owner=owner)
            return
        elif effect == "replay_trash_unit":
            resume = reveal.get("resume") or {"phase": "main", "actor": reveal["owner"], "passes": 0}
            state["reveal"] = None
            state["phase"], state["actor"], state["passes"] = resume["phase"], resume["actor"], resume.get("passes", 0)
            if selected:
                owner = reveal["owner"]
                row = state["players"][owner]
                card = selected[0]
                if card in row["trash"]:
                    row["trash"].remove(card)
                    row["hand"].append(card)
                    code = state["cards"][card]["code"]
                    payments = self._payments(state, owner, 0, self.cards[code]["domains"],
                                              self.cards[code]["power_cost"])
                    if payments:
                        self._pay(row, 0, payments[0])
                        self.apply(state, Action.make("play_unit", card=card,
                                                      location=f"base:{owner}", accelerate=False,
                                                      payment=[], enter_target=None, ignore_cost=True),
                                   rng)
                    else:
                        row["hand"].remove(card)
                        row["trash"].append(card)
            self._cleanup(state, rng)
            return
        elif effect == "guerrilla_return_hidden":
            row = state["players"][reveal["owner"]]
            for uid in selected:
                if uid in row["trash"] and self._is_hidden_code(state["cards"][uid]["code"]):
                    row["trash"].remove(uid)
                    row["hand"].append(uid)
            row["free_hide_turn"] = True
            item = reveal.get("item")
            if item is not None:
                item["reveal_done"] = True
                state["chain"].append(item)
        resume = reveal.get("resume") or {"phase": "main", "actor": state["turn_player"], "passes": 0}
        state["reveal"] = None
        # An optional effect that opened this reveal has already been removed
        # from ``optional``.  Once the final reveal closes, consume the saved
        # return marker as well; otherwise validation sees an empty optional
        # queue while the phase still points at ``optional``.
        if resume.get("phase") == "optional" and not state.get("optional"):
            restored = state.pop("optional_return", None)
            if restored is not None:
                resume = restored
        if state.get("chain") or resume["phase"] == "chain":
            state["phase"], state["actor"], state["passes"] = "chain", resume.get("actor", state["actor"]), 0
            self._finish_resolution(state)
        else:
            state["phase"], state["actor"], state["passes"] = resume["phase"], resume["actor"], resume.get("passes", 0)
        self._cleanup(state, rng)

    def _resolve_optional(self, state, item, rng):
        player = item["player"]
        effect = item["effect"]
        if effect == "draven_might":
            source = self._unit(state, item.get("source"))
            row = state["players"][player]
            if (source is None or source["owner"] != player
                    or source["location"] != item.get("field")
                    or not row["power"]):
                return True
            row["power"].pop(0)
            source["temporary"] += 2
            return True
        if effect == "loyal_pup_move":
            source = self._unit(state, item.get("source"))
            destination = item.get("destination")
            if (source is None or source["owner"] != player
                    or source["location"] != f"base:{player}"
                    or not self._is_field(state, destination)):
                return True
            source["location"] = destination
            source["exhausted"] = True
            source["move_count"] = source.get("move_count", 0) + 1
            return True
        if effect == "fan_return_attacker":
            source = self._unit(state, item.get("source"))
            field = item.get("field")
            candidates = [unit["id"] for unit in state["units"]
                          if unit["owner"] != player and unit["location"] == field]
            if source is None or source["owner"] != player or source["location"] != field:
                return True
            if not candidates:
                return True
            state["decision"] = {
                "kind": "target", "player": player, "targets": candidates,
                "item": {"effect": "fan_return_attacker", "owner": player,
                          "source": source["id"], "field": field},
                "optional_fan_target": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "return_small_field_unit":
            candidates = [unit["id"] for unit in state["units"]
                          if self._is_field(state, unit["location"])
                          and self.might(state, unit) <= 3
                          and unit["id"] != item.get("source")]
            if not candidates:
                return True
            state["decision"] = {
                "kind": "target", "player": player,
                "targets": candidates,
                "item": {"effect": "return_field_unit", "owner": player,
                          "source": item.get("source")},
                "optional_return_field_unit": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "return_self":
            source = self._unit(state, item.get("source"))
            row = state["players"][player]
            if source is None or source["owner"] != player or row["energy"] < 1:
                return True
            row["energy"] -= 1
            state["units"].remove(source)
            self._hand_unit_card(state, source)
            return True
        if effect == "miss_fortune_ready":
            source = self._unit(state, item.get("source"))
            candidates = [unit["id"] for unit in self._units(state, player)
                          if unit["id"] != item.get("source") and unit["exhausted"]]
            if source is None or source["owner"] != player or not candidates:
                return True
            if item.get("target") is None:
                state["decision"] = {
                    "kind": "target", "player": player, "targets": candidates,
                    "item": {"effect": "miss_fortune_ready", "owner": player,
                              "source": source["id"]},
                    "optional_ready_effect": True,
                }
                state["phase"], state["actor"], state["passes"] = "decision", player, 0
                return False
            target = self._unit(state, item.get("target"))
            if target is not None and target["owner"] == player and target["id"] != source["id"]:
                self._ready_unit(state, target)
            return True
        if effect == "stealthy_pursuer_follow":
            source = self._unit(state, item.get("source"))
            destination = item.get("destination")
            if (source is None or source["code"] != "OGN-177"
                    or source["owner"] != player or source["exhausted"]):
                return True
            # This is the same movement event as the initiating move, but it
            # must not recursively offer the same Pursuer again.  Apply the
            # ordinary movement state (including automatic exhaustion) while
            # retaining the already established showdown context.
            origin = source.get("location")
            source["location"], source["exhausted"] = destination, True
            source["move_count"] = source.get("move_count", 0) + 1
            if self._is_field(state, origin) and state["fields"][origin]["code"] == "OGN-277":
                source["temporary"] += 1
            self._cleanup(state, rng)
            return True
        if effect == "solari_shrine_draw":
            source = item.get("source")
            if item.get("copied"):
                heimer = self._unit(state, source)
                if heimer is None or heimer["code"] != "OGN-111" or heimer["exhausted"]:
                    return True
                heimer["exhausted"] = True
            else:
                gear = next((gear for gear in state["players"][player]["gear"]
                             if gear["id"] == source and gear["code"] == "OGN-072"
                             and not gear["exhausted"]), None)
                if gear is None:
                    return True
                gear["exhausted"] = True
            self._draw(state, player, 1, rng)
            return True
        if effect in {"mistfall_ready", "heimer_mistfall_ready"}:
            target = self._unit(state, item.get("target"))
            row = state["players"][player]
            source = (self._unit(state, item.get("source")) if item.get("copied") else
                      next((gear for gear in row["gear"]
                            if gear["id"] == item.get("source") and gear["code"] == "OGN-152"), None))
            if target is None or source is None or source.get("exhausted"):
                return True
            power_index = next((index for index, power in enumerate(row["power"])
                                if power in {"body", "any"}), None)
            if power_index is None:
                return True
            row["power"].pop(power_index)
            source["exhausted"] = True
            self._ready_unit(state, target)
            return True
        if effect in {"boss_save", "heimer_boss_save"}:
            target = self._unit(state, item.get("target"))
            row = state["players"][player]
            if target is None or target.get("buff", 0) <= 0:
                return True
            power_index = next((index for index, power in enumerate(row["power"])
                                if power in DOMAINS or power == "any"), None)
            if power_index is None:
                return True
            if item.get("copied"):
                source = self._unit(state, item.get("source"))
                if source is None or source["code"] != "OGN-111" or source["exhausted"]:
                    return True
            else:
                source = state["players"][player]
                if source["legend"] != "OGN-269" or source["legend_exhausted"]:
                    return True
            target.pop("death_replacement", None)
            row["power"].pop(power_index)
            if item.get("copied"):
                source["exhausted"] = True
            else:
                row["legend_exhausted"] = True
            target["buff"] = 0
            target["damage"] = 0
            target["location"] = f"base:{player}"
            target["exhausted"] = True
            self._complete_death_replacement(state, target["id"])
            return True
        if effect == "armory_save":
            target = self._unit(state, item.get("target"))
            row = state["players"][player]
            if target is None or target["owner"] != player:
                return True
            power_index = next((index for index, power in enumerate(row["power"])
                                if power == "fury"), None)
            if power_index is None:
                target.pop("death_replacement", None)
                return True
            row["power"].pop(power_index)
            target.pop("death_replacement", None)
            target["damage"] = 0
            target["location"] = f"base:{player}"
            target["exhausted"] = True
            self._complete_death_replacement(state, target["id"])
            return True
        if effect == "kill_gear":
            gears = [gear["id"] for row in state["players"] for gear in row.get("gear", [])]
            if not gears:
                return True
            state["decision"] = {
                "kind": "target", "player": player, "targets": gears,
                "item": {"effect": "kill_gear_optional", "owner": player,
                          "source": item.get("source")},
                "optional_gear_effect": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "kill_cheap_gear":
            gears = [gear["id"] for row in state["players"]
                     for gear in row.get("gear", [])
                     if self.cards.get(gear["code"], {}).get("energy", 99) <= 1]
            if not gears:
                return True
            state["decision"] = {
                "kind": "target", "player": player, "targets": gears,
                "item": {"effect": "kill_gear_optional", "owner": player,
                          "source": item.get("source")},
                "optional_gear_effect": True,
                "play_gold": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "return_card_from_trash":
            row = state["players"][player]
            cards = [uid for uid in row["trash"]
                     if self.cards.get(state["cards"][uid]["code"], {}).get("type")
                     in {"unit", "gear"}]
            if not cards:
                return True
            state["decision"] = {
                "kind": "target", "player": player, "targets": cards,
                "item": {"effect": "return_card_from_trash", "owner": player},
                "optional_return_card": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "draw_or_buff":
            state["decision"] = {
                "kind": "choice", "player": player,
                "options": ["draw", "buff"],
                "item": {"effect": "draw_or_buff", "owner": player,
                          "source": item.get("source")},
                "draw_or_buff": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "replay_trash_unit":
            code = item.get("code")
            candidates = [uid for uid in state["players"][player]["trash"]
                          if self.cards[state["cards"][uid]["code"]]["type"] == "unit"
                          and (code != "OGN-226" or (
                              self.cards[state["cards"][uid]["code"]]["energy"] <= 3
                              and self.cards[state["cards"][uid]["code"]]["power_cost"] <= 1))]
            if not candidates:
                return True
            self._open_reveal(state, owner=player, cards=candidates, mode="select",
                              chooser=player, minimum=0, maximum=1,
                              effect="replay_trash_unit", choices=candidates, rng=rng)
            return False
        if effect == "play_flame_chompers":
            row = state["players"][player]
            card = item.get("card")
            if card not in row["trash"]:
                return True
            power_index = next((index for index, power in enumerate(row["power"])
                                if power == "fury"), None)
            if power_index is None:
                return True
            row["power"].pop(power_index)
            row["trash"].remove(card)
            row["hand"].append(card)
            self._free_play_revealed_card(
                state, player, card, None, rng,
                ignore_energy=True, card_owner=player)
            return True
        if effect == "ava_play_hidden":
            candidates = [uid for uid in item.get("candidates", [])
                          if uid in state["players"][player]["hand"]]
            if not candidates:
                return True
            state["decision"] = {"kind": "hand_card", "player": player,
                                  "cards": candidates, "item": item,
                                  "ava_play_hidden": True}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "kaisa_replay_spell":
            row = state["players"][player]
            points = state["points"][player]
            candidates = [uid for uid in row["trash"]
                          if self.cards[state["cards"][uid]["code"]]["type"] == "spell"
                          and self.cards[state["cards"][uid]["code"]]["energy"] < points]
            if not candidates:
                return True
            self._open_reveal(state, owner=player, cards=candidates, mode="select",
                              chooser=player, minimum=0, maximum=1,
                              effect="kaisa_replay_spell", choices=candidates,
                              item={"effect": "kaisa_replay_spell", "owner": player}, rng=rng)
            return False
        if effect == "adaptatron_conquer":
            source = self._unit(state, item.get("source"))
            gears = [gear["id"] for gear in state["players"][player]["gear"]]
            if source is None or not gears:
                return True
            state["decision"] = {"kind": "target", "player": player,
                                  "targets": gears, "item": {"effect": "adaptatron_conquer",
                                  "owner": player, "source": source["id"]},
                                  "adaptatron_gear": True}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "qiyana_conquer":
            state["decision"] = {"kind": "choice", "player": player,
                                  "options": ["draw", "channel"],
                                  "item": {"effect": "qiyana_conquer", "owner": player}}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "yone_conquer_damage":
            source = self._unit(state, item.get("source"))
            candidates = [unit["id"] for unit in self._units(state, 1 - player,
                                                               f"base:{1 - player}")]
            if source is None or source["owner"] != player or not candidates:
                return True
            state["decision"] = {
                "kind": "target", "player": player, "targets": candidates,
                "item": {"effect": "yone_conquer_damage", "owner": player,
                          "source": source["id"]},
                "optional_yone_target": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        if effect == "channel_rune":
            self._channel_rune(state, player, exhausted=True)
        elif effect == "return_champion":
            row = state["players"][player]
            card = item.get("candidate")
            if card in row["trash"] and not row["champion"]:
                row["trash"].remove(card)
                row["champion"].append(card)
        elif effect == "spend_buff_draw":
            target = self._unit(state, item.get("target"))
            if target is None:
                candidates = [unit["id"] for unit in self._units(state, player)
                              if unit["buff"]]
                if not candidates:
                    return True
                state["decision"] = {"kind": "target", "player": player,
                                      "targets": candidates,
                                      "item": {"effect": "spend_buff_draw", "owner": player},
                                      "optional_target_effect": True}
                state["phase"], state["actor"], state["passes"] = "decision", player, 0
                return False
            if target is not None and target["owner"] == player and target["buff"]:
                target["buff"] = 0
                self._draw(state, player, 1, rng)
        elif effect == "ready_runes":
            for rune in state["players"][player]["runes"][:2]:
                rune["exhausted"] = False
        elif effect == "recycle_top_two":
            row = state["players"][player]
            top = list(row["main"][:2])
            if top:
                self._open_reveal(state, owner=player, cards=top, mode="select",
                                  chooser=player, minimum=0, maximum=len(top),
                                  effect="recycle_top_two", choices=top, rng=rng)
                return False
        elif effect == "albus_channel":
            source = self._unit(state, item.get("source"))
            candidates = [unit["id"] for unit in self._units(state, player)
                          if unit["buff"]]
            if source is None or not candidates:
                return True
            state["decision"] = {
                "kind": "target", "player": player, "targets": candidates,
                "multi": True, "min": 0,
                "max": sum(unit["buff"] for unit in self._units(state, player)),
                "selected": [], "allow_repeat": True,
                "item": {"effect": "albus_channel", "owner": player,
                          "source": source["id"]},
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
        elif effect == "reaver_recall":
            field = state.get("battle", {}).get("field")
            targets = self._units(state, player, field) if self._is_field(state, field) else []
            if targets:
                state["decision"] = {
                    "kind": "target", "player": player,
                    "targets": [unit["id"] for unit in targets],
                    "item": {"effect": "reaver_recall_target", "owner": player},
                    "resume": "close_showdown",
                }
                state["phase"], state["actor"] = "decision", player
                return False
        elif effect == "wildclaw_ready":
            source = self._unit(state, item.get("source"))
            candidates = [unit["id"] for unit in self._units(state, player)
                          if unit["id"] != item.get("source") and unit["buff"]]
            if source is None or not candidates:
                return True
            state["decision"] = {
                "kind": "target", "player": player, "targets": candidates,
                "item": {"effect": "wildclaw_ready", "owner": player,
                          "source": source["id"]},
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return False
    def _recycle_one_rune(self, state, player):
        row = state["players"][player]
        if not row["runes"]:
            return False
        rune = row["runes"].pop(0)
        row["power"].extend(self.cards[rune["code"]]["domains"])
        row["rune_deck"].append({**rune, "exhausted": False})
        return True

    def _score(self, state, player, field, method, rng, *, uncontrolled=False):
        if (method in {"hold", "conquer"}
                and any(unit["owner"] != player
                        and unit["location"] == field
                        and (self._card_implementation(unit["code"]) is not None)
                        and self._card_implementation(unit["code"]).global_effect == "opponents_cant_score"
                        for unit in state["units"])):
            return
        board = Scoreboard(state["points"], [set(s) for s in state["scored"]], state["victory"], len(state["fields"]))
        result = board.score(player, field, method=method)
        state["scored"] = [sorted(s) for s in board.scored]
        if result is not None and method == "hold":
            state["points"][player] += sum(u["code"] == "OGN-066"
                                            for u in self._units(state, player, field))
            if result == "point":
                state.setdefault("hold_points", [0, 0])[player] += 1
        if result in {"point", "draw"} and method == "hold":
            for unit in self._units(state, player, field):
                implementation = self._card_implementation(unit["code"])
                if implementation and implementation.hold_effect == "draw_two":
                    self._draw(state, player, 2, rng)
                if implementation and implementation.hold_effect == "play_two_gold_gear":
                    self._play_gold_gear_token(state, player, exhausted=True)
                    self._play_gold_gear_token(state, player, exhausted=True)
                if implementation and implementation.hold_effect == "play_mech_token":
                    self._new_unit(state, "SFD-T05", player, f"base:{player}")
                if (implementation
                        and implementation.hold_effect == "optional_return_card_from_trash"
                        and any(self.cards.get(state["cards"][uid]["code"], {}).get("type")
                                in {"unit", "gear"}
                                for uid in state["players"][player]["trash"])):
                    self._queue_optional(state, player, "return_card_from_trash",
                                         source=unit["id"])
        # These battlefield triggers are intentionally resolved at the score
        # event, after the point/draw result is known.  The closed engine has
        # no gear zone yet, so the effects here only touch existing card
        # resources and units.
        if result in {"point", "draw"} and method == "hold":
            code = state["fields"][field]["code"]
            if code == "OGN-275":
                self._new_unit(state, TOKEN, player, f"base:{player}")
            elif code == "OGN-280":  # Grove of the God-Willow
                self._draw(state, player, 1, rng)
            elif code == "OGN-283":
                candidates = [unit["id"] for unit in self._units(state, player, field)
                              if not unit["buff"]]
                if len(candidates) == 1:
                    self._apply_buff(state, self._unit(state, candidates[0]))
                elif len(candidates) > 1:
                    state["decision"] = {"kind": "target", "player": player,
                                          "targets": candidates,
                                          "item": {"effect": "navori_buff", "owner": player},
                                          "score_target": True}
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
                    return
            elif code == "OGN-281" and not state["players"][player]["champion"]:
                chosen = self.decks[player]["chosen_champion"]
                row = state["players"][player]
                candidate = next((uid for uid in row["trash"]
                                  if state["cards"][uid]["code"] == chosen), None)
                if candidate is not None:
                    self._queue_battlefield_optional(
                        state, player, "return_champion", candidate=candidate)
            elif code == "OGN-286":
                for _ in range(sum(u["code"] == "OGN-039" for u in self._units(state, player, field))):
                    self._draw(state, player, 1, rng)
            elif code == "OGN-293" and len(self._units(state, player, field)) >= 7:
                state["winner"] = player
            elif code == "OGN-288" and state["players"][player]["rune_deck"]:
                self._queue_battlefield_optional(state, player, "channel_rune")
        if result in {"point", "draw"} and method == "hold":
            for unit in list(self._units(state, player, field)):
                if unit["code"] == "OGN-067":
                    state["units"].remove(unit)
                    self._hand_unit_card(state, unit)
        if result in {"point", "draw"} and method == "conquer":
            code = state["fields"][field]["code"]
            if any(unit["code"] == "OGN-155" for unit in self._units(state, player, field)):
                self._queue_optional(state, player, "qiyana_conquer")
            for unit in self._units(state, player, field):
                if unit["code"] == "OGN-056":
                    self._queue_optional(state, player, "adaptatron_conquer", source=unit["id"])
                if unit["code"] == "OGN-112":
                    self._queue_optional(state, player, "kaisa_replay_spell", source=unit["id"])
                implementation = self._card_implementation(unit["code"])
                if implementation and implementation.conquer_effect == "play_gold_gear":
                    self._play_gold_gear_token(state, player, exhausted=True)
                if (implementation and implementation.conquer_effect == "ready_self_once"
                        and unit.get("conquer_ready_turn") != state["turn"]):
                    unit["conquer_ready_turn"] = state["turn"]
                    self._ready_unit(state, unit)
                if (implementation
                        and implementation.conquer_effect == "damage_enemy_base_by_might"
                        and uncontrolled):
                    self._queue_optional(state, player, "yone_conquer_damage",
                                         source=unit["id"])
                if implementation and implementation.conquer_effect == "buff_self":
                    self._apply_buff(state, unit)
                if (implementation and implementation.conquer_effect == "return_self"
                        and state["players"][player]["energy"] >= 1):
                    self._queue_optional(state, player, "return_self", source=unit["id"])
            if code == "OGN-282":
                # Monastery's optional draw lets the player choose which
                # friendly buff to spend.  Do not silently take the first
                # matching unit; the optional resolver opens a target window
                # when more than one legal unit exists (and also handles the
                # single-target case consistently).
                if any(u["buff"] for u in self._units(state, player, field)):
                    self._queue_battlefield_optional(state, player, "spend_buff_draw")
            elif code == "OGN-287":
                self._recycle_one_rune(state, player)
            elif code == "OGN-289":
                # The battlefield text checks the conquer event now but
                # resolves at the end of this turn. Keep a pending marker so
                # the effect cannot ready runes immediately during scoring.
                state.setdefault("targon_pending", []).append(player)
            elif code == "OGN-291":
                self._queue_battlefield_optional(state, player, "recycle_top_two")
            elif code == "OGN-298":  # Zaun Warrens
                row = state["players"][player]
                if row["hand"]:
                    state["decision"] = {"kind": "discard", "player": player,
                                          "remaining": 1, "zaun_warrens": True}
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
                    return
        if result == "draw":
            self._draw(state, player, 1, rng)
        self._cleanup(state, rng)

    def _start_turn(self, state, rng):
        state["turn"] += 1
        player = state["turn_player"]
        state["actor"], state["phase"] = player, "main"
        # Optional legend triggers are decided in the turn they occur; never
        # carry an unchosen opportunity into a later turn.
        state["legend_options"] = []
        state["scored"] = [[], []]
        state["hold_points"] = [0, 0]
        state["dreaming_tree_used"] = [False] * len(state["fields"])
        state["rally_effects"] = []
        for row in state["players"]:
            row["played"] = 0
            row["finalized_played"] = 0
            row["finalized_cards"] = []
            row["ready_play"] = False
            row["buff_bonus"] = 0
            row["discarded_this_turn"] = False
            row["cards_locked_turn"] = False
            row["spell_discount"] = 0
            row["free_hide_turn"] = False
        row = state["players"][player]
        row["legend_exhausted"] = False
        if row["turns"] == 0 and not state["beginning_awarded"][player]:
            state["points"][player] += sum(field["code"] == "OGN-290"
                                            for field in state["fields"])
            state["beginning_awarded"][player] = True
            if any(field["code"] == "OGN-284" for field in state["fields"]):
                self._channel_rune(state, player)
        # Temporary units are killed at the start of their controller's
        # Beginning Phase, before scoring and before new resources are added.
        for unit in list(self._units(state, player)):
            if unit.get("temporary_unit"):
                state["units"].remove(unit)
                self._trash_unit_card(state, unit)
        # Temporary gear follows the same Beginning Phase expiry as temporary
        # units (RUP5 Temporary): remove it before scoring and return the
        # physical card to its owner’s trash.
        for gear in list(row["gear"]):
            if gear.get("temporary"):
                row["gear"].remove(gear)
                self._trash_gear_card(state, gear)
        for rune in row["runes"]:
            rune["exhausted"] = False
        for unit in self._units(state, player):
            unit["exhausted"] = False
            unit["stunned"] = False
            unit["temporary_ganking"] = False
            unit["udyr_choices"] = []
            unit["move_count"] = 0
        # Loose Cannon has a forced draw; this closed card pool has no
        # Fury/Chaos Reactions, so the forced beginning trigger can settle here.
        if row["legend"] == "OGN-251" and len(row["hand"]) <= 1:
            self._draw(state, player, 1, rng)
            self._cleanup(state, rng)
            if state["winner"] is not None:
                return
        # A player may control multiple battlefields whose Hold abilities
        # trigger from this Beginning Phase.  Generate all of those score
        # events before exposing any optional decision so the player can order
        # the simultaneous abilities in one window.
        state["collecting_battlefield_triggers"] = True
        try:
            for field, obj in enumerate(state["fields"]):
                if obj["controller"] == player:
                    self._score(state, player, field, "hold", rng)
                    if state["winner"] is not None:
                        return
        finally:
            state.pop("collecting_battlefield_triggers", None)
        if state.get("decision") is None and state.get("reveal") is None:
            self._flush_deferred_battlefield_optionals(state)
        # Mushroom Pouch checks the facedown zone at the beginning of its
        # controller's turn, after beginning-of-turn cleanup and before draw.
        if any(g["code"] == "OGN-101" for g in row["gear"]):
            if any(h.get("field") is not None for h in row.get("hidden", [])):
                self._draw(state, player, 1, rng)
        count = channel_count(first_turn=row["turns"] == 0, second_player=player != state["first"],
                              available=len(row["rune_deck"]))
        row["runes"].extend(row["rune_deck"][:count])
        del row["rune_deck"][:count]
        row["turns"] += 1
        self._draw(state, player, 1, rng)
        # 316.3: both pools empty at the start of Main Phase, after Draw.
        for obj in state["players"]:
            obj["energy"], obj["power"] = 0, []
        if state["phase"] == "main" and any(unit["code"] == "OGN-109" for unit in self._units(state, player)) and row["trash"]:
            self._open_reveal(state, owner=player, cards=list(row["trash"]),
                              mode="select", chooser=player, minimum=0, maximum=min(3, len(row["trash"])),
                              effect="dr_mundo_recycle", choices=list(row["trash"]), rng=rng)
            return
        self._cleanup(state, rng)

    def _hidden_actions(self, state):
        player = state["actor"]
        row = state["players"][player]
        result = []
        if state["phase"] == "main" and state["turn_player"] == player and not self._cards_locked(state, player):
            open_fields = [field for field, obj in enumerate(state["fields"])
                           if obj["controller"] == player
                           and sum(h["field"] == field for owner in state["players"]
                                   for h in owner.get("hidden", []))
                               < (2 if obj["code"] == "OGN-278" else 1)]
            for card in row["hand"] + row["champion"]:
                code = state["cards"][card]["code"]
                if not self._is_hidden_code(code):
                    continue
                for field in open_fields:
                    if row.get("free_hide_turn"):
                        result.append(Action.make("hide_card", card=card, field=field,
                                                  payment=[], ignore_cost=True))
                    else:
                        for payment in self._payments(state, player, 0, DOMAINS, 0, 1):
                            result.append(Action.make("hide_card", card=card, field=field, payment=payment))
                    if row["legend"] == "OGN-263" and row["energy"] >= 1:
                        result.append(Action.make("hide_card", card=card, field=field,
                                                  payment=[], use_energy=True))
        if self._cards_locked(state, player):
            return result
        for hidden in row.get("hidden", []):
            if hidden["turn"] >= state["turn"]:
                continue
            field = hidden["field"]
            code = hidden["code"]
            if any(u["owner"] != player and u["code"] == "OGN-018"
                   and u["location"] == field for u in state["units"]):
                continue
            if code in {"OGN-053", "OGN-168", "OGN-213", "OGN-097", "OGN-057"}:
                if code == "OGN-053":
                    candidates = [u["id"] for u in self._units(state, player, field)]
                elif code == "OGN-097":
                    candidates = [u["id"] for u in self._units(state, location=field)]
                elif code == "OGN-057":
                    candidates = [u["id"] for u in self._units(state, location=field)]
                else:
                    candidates = [u["id"] for u in self._units(state, location=field)]
                if candidates:
                    result.append(Action.make("play_hidden_targeted", card=hidden["id"], field=field,
                                              target_candidates=candidates, target_min=1, target_max=1))
            elif code == "OGN-199":
                # Tideturner is the Hidden exception in RUP5 811.1.d.3:
                # its printed target explicitly says "at another location",
                # so the target is any friendly unit at a different location
                # rather than only the battlefield where it was hidden.
                candidates = [u["id"] for u in self._units(state, player)
                              if u["id"] != hidden["id"]
                              and u["location"] != field]
                if candidates:
                    result.append(Action.make("play_hidden_targeted", card=hidden["id"], field=field,
                                              target_candidates=candidates, target_min=1, target_max=1))
            elif code == "OGN-220":
                # Facebreaker is a Hidden exception with a manual two-target
                # choice: one friendly and one enemy unit at the original
                # battlefield.  Keep the legal pair set in the decision so
                # the UI can select targets one at a time and reject an
                # invalid second click before the card enters the chain.
                pairs = [[friendly["id"], enemy["id"]]
                         for friendly in self._units(state, player, field)
                         for enemy in self._units(state, 1 - player, field)]
                if pairs:
                    candidates = sorted({uid for pair in pairs for uid in pair})
                    result.append(Action.make(
                        "play_hidden_targeted", card=hidden["id"], field=field,
                        target_candidates=candidates, target_min=2, target_max=2,
                        target_pairs=pairs))
            elif code == "OGN-256":
                # Fox-Fire is a Hidden multi-target spell. Its initial target
                # choices are restricted to the battlefield where it was
                # hidden; resolution applies the ordinary Fox-Fire group
                # recheck to those original targets.
                candidates = [u["id"] for u in self._units(state, location=field)]
                if candidates:
                    result.append(Action.make(
                        "play_hidden_targeted", card=hidden["id"], field=field,
                        target_candidates=candidates, target_min=0,
                        target_max=len(candidates), multi=True,
                        target_might_limit=4, same_location=True))
                else:
                    result.append(Action.make("play_hidden", card=hidden["id"], field=field, targets=[]))
            else:
                result.append(Action.make("play_hidden", card=hidden["id"], field=field, targets=[]))
        return result

    @staticmethod
    def _target_pair_matches(decision, selected):
        """Whether a Hidden multi-target selection is a complete legal pair."""
        pairs = decision.get("target_pairs") or []
        if decision.get("ordered_pairs"):
            return any(list(selected) == list(pair) for pair in pairs)
        selected_set = set(selected)
        return any(selected_set == set(pair) and len(selected) == len(pair)
                   for pair in pairs)

    @staticmethod
    def _target_pair_extendable(decision, selected):
        """Whether the current selection can still become one legal pair."""
        pairs = decision.get("target_pairs") or []
        if decision.get("ordered_pairs"):
            return any(list(pair[:len(selected)]) == list(selected)
                       and len(selected) < len(pair) for pair in pairs)
        selected_set = set(selected)
        return any(selected_set <= set(pair) and len(selected) < len(pair)
                   for pair in pairs)

    def _play_hidden_from_decision(self, state, player, info, targets, rng):
        """Remove a ready Hidden card and play it with confirmed targets."""
        hidden = next((h for h in state["players"][player]["hidden"]
                       if h["id"] == info["card"]), None)
        if hidden is None or hidden["turn"] >= state["turn"]:
            raise ValueError("hidden card is no longer available")
        state["players"][player]["hidden"].remove(hidden)
        state["players"][player]["hand"].append(hidden["card"])
        code = hidden["code"]
        kind = ("play_unit" if self.cards[code]["type"] == "unit"
                else "play_gear" if self.cards[code]["type"] == "gear"
                else "play_spell")
        if kind == "play_unit":
            nested = Action.make(kind, card=hidden["card"], location=hidden["field"],
                                  accelerate=False, payment=[],
                                  enter_target=(targets[0] if targets else None),
                                  ignore_cost=True, hidden_field=hidden["field"])
        elif kind == "play_gear":
            nested = Action.make(kind, card=hidden["card"], payment=[], ignore_energy=True)
        else:
            nested = Action.make(kind, card=hidden["card"], targets=list(targets),
                                 destination=None, spend_buff=None, payment=[],
                                 ignore_cost=True, hidden_field=hidden["field"])
        self.apply(state, nested, rng)

    def _heimer_has_copy(self, state, player, source_kind, card_code):
        """Whether a ready Heimer has a registered exhaust ability from a source."""
        if not self.abilities.copyable_for_heimer(source_kind, card_code):
            return False
        if source_kind == "unit":
            source_present = any(unit["code"] == card_code
                                 for unit in self._units(state, player))
        elif source_kind == "gear":
            source_present = any(gear["code"] == card_code
                                 for gear in state["players"][player]["gear"])
        elif source_kind == "legend":
            source_present = state["players"][player]["legend"] == card_code
        else:
            source_present = False
        return source_present and any(unit["code"] == "OGN-111" and not unit["exhausted"]
                                      for unit in self._units(state, player))

    def _registry_target_candidates(self, state, player, spec):
        """Build legal target IDs for a declarative activated ability.

        This is intentionally shared by native and Heimer-copied abilities so
        future registrations add a target mode instead of another card-code
        branch.  The resolver still performs final legality checks at apply
        time because the board can change between action generation and use.
        """
        mode = spec.target_mode
        if mode in {"none", "choice"}:
            return []
        if mode == "unit":
            return [u["id"] for u in state["units"]]
        if mode in {"unit_at_battlefield", "unit_any_field"}:
            return [u["id"] for u in state["units"] if self._is_field(state, u["location"])]
        if mode == "unit_at_battlefield":
            return [u["id"] for u in state["units"] if self._is_field(state, u["location"])]
        if mode in {"friendly_unit", "friendly_exhausted_unit"}:
            return [u["id"] for u in self._units(state, player)
                    if mode != "friendly_exhausted_unit" or u["exhausted"]]
        if mode == "friendly_unit_or_gear":
            return [u["id"] for u in self._units(state, player)] + [g["id"] for g in state["players"][player]["gear"]]
        if mode in {"friendly_field_unit", "friendly_unit_at_battlefield"}:
            return [u["id"] for u in self._units(state, player) if self._is_field(state, u["location"])]
        if mode == "friendly_gear_unit_hidden":
            row = state["players"][player]
            return ([u["id"] for u in self._units(state, player)]
                    + [g["id"] for g in row["gear"]]
                    + [h["id"] for h in row.get("hidden", [])])
        if mode == "teemo_in_champion_or_board":
            row = state["players"][player]
            return [uid for uid in row["champion"] if self.cards[state["cards"][uid]["code"]]["code"] == "OGN-121"] + [
                u["id"] for u in self._units(state, player) if u["code"] == "OGN-121"]
        return []

    def _registry_copy_available(self, state, player, heimer, spec):
        """Check costs and timing common to all Heimer copied abilities."""
        if heimer is None or heimer["owner"] != player or heimer["code"] != "OGN-111" or heimer["exhausted"]:
            return False
        # Triggered/replacement E abilities are registered for event-driven
        # resolution, not exposed as free-standing main-phase actions.
        if spec.timing in {"triggered", "replacement", "static"}:
            return False
        # A copied Reaction ability still has the printed Reaction timing.
        # In particular, resource abilities on Daughter of the Void, Hand of
        # Noxus, and the Seal Gear must not become free actions during Main.
        # They are offered only while a Chain or Showdown reaction window is
        # open (the active actor is already enforced by legal_actions()).
        accelerate_window = (state.get("phase") == "decision"
                             and (state.get("decision") or {}).get("accelerate"))
        if spec.timing == "reaction" and state.get("phase") not in {"chain", "showdown"} \
                and not accelerate_window:
            return False
        row = state["players"][player]
        if spec.action_kind == "unit_caitlyn" and not self._is_field(state, heimer["location"]):
            return False
        if spec.action_kind == "legend_energy" and not self._played_for_legion(state, player):
            return False
        if spec.action_kind == "legend_channel":
            if not row["rune_deck"] or not any(option["owner"] == player for option in state.get("legend_options", [])):
                return False
        if spec.action_kind in {"legend_recruit", "legend_buff", "legend_teemo"} and row["energy"] < 1:
            return False
        if spec.action_kind == "legend_move" and row["energy"] < 2:
            return False
        if spec.action_kind == "gear_grab" and (row["energy"] < 1 or len(row["trash"]) < 3):
            return False
        if spec.action_kind == "gear_armory_protect" and not row["hand"]:
            return False
        if spec.action_kind == "gear_baited_hook" and (row["energy"] < 1 or "order" not in row["power"]):
            return False
        if spec.action_kind == "gear_forge_recycle" and not row["trash"]:
            return False
        return True

    def _heimer_registry_actions(self, state, player, heimer):
        """Expose every registered exhaust ability Heimer can currently use."""
        result = []
        row = state["players"][player]
        sources = []
        for unit in self._units(state, player):
            if unit["id"] != heimer["id"]:
                sources.append(("unit", unit["code"], unit["id"]))
        sources.append(("legend", row["legend"], f"legend:{player}"))
        sources.extend(("gear", gear["code"], gear["id"]) for gear in row["gear"])
        seen = set()
        for source_kind, source_code, origin in sources:
            for spec in self.abilities.copyable_for_heimer(source_kind, source_code):
                key = (spec.ability_id, origin)
                if key in seen or not self._registry_copy_available(state, player, heimer, spec):
                    continue
                seen.add(key)
                candidates = self._registry_target_candidates(state, player, spec)
                if spec.target_mode not in {"none", "choice"} and not candidates:
                    continue
                if spec.target_mode in {"none", "choice"}:
                    result.append(Action.make("ability_activate", ability_id=spec.ability_id,
                                              source=heimer["id"], origin=origin,
                                              copied_from=source_code))
                else:
                    result.append(Action.make("ability_targeted", ability_id=spec.ability_id,
                                              source=heimer["id"], origin=origin,
                                              copied_from=source_code,
                                              target_candidates=candidates))
        return result

    def _registry_source_for(self, state, player, spec, origin):
        if origin.startswith("legend:"):
            return {"id": origin, "code": state["players"][player]["legend"], "owner": player,
                    "kind": "legend", "exhausted": state["players"][player]["legend_exhausted"]}
        if spec.source_kind == "gear":
            return next((g for g in state["players"][player]["gear"] if g["id"] == origin), None)
        return self._unit(state, origin)

    def _registry_event_sources(self, state, player, ability_id):
        """Return ready native or Heimer sources for a triggered E ability."""
        spec = self.abilities.get(ability_id)
        row = state["players"][player]
        sources = []
        source_present = False
        metadata = {
            "ability_id": ability_id,
            "timing": spec.timing,
            "event": spec.event,
            "target_spec": dict(spec.target_spec or {}),
            "continuation": spec.continuation,
            "replacement_priority": spec.replacement_priority,
            "copy_policy": spec.copy_policy,
        }
        if spec.source_kind == "gear":
            source_present = any(gear["code"] in spec.source_codes for gear in row["gear"])
            for gear in row["gear"]:
                if gear["code"] in spec.source_codes and not gear["exhausted"]:
                    sources.append({"id": gear["id"], "kind": "gear", "copied": False,
                                    **metadata})
        elif spec.source_kind == "legend":
            source_present = row["legend"] in spec.source_codes
            if row["legend"] in spec.source_codes and not row["legend_exhausted"]:
                sources.append({"id": f"legend:{player}", "kind": "legend", "copied": False,
                                **metadata})
        if spec.copyable and source_present:
            for unit in self._units(state, player):
                if unit["code"] == "OGN-111" and not unit["exhausted"]:
                    sources.append({"id": unit["id"], "kind": "unit", "copied": True,
                                    **metadata})
        # Source order is deterministic for replay.  When several sources
        # belong to the same controller, legal_actions exposes an explicit
        # optional-order window so the player may choose a different order.
        return sorted(sources, key=lambda source: (bool(source["copied"]), str(source["id"])))

    def _registry_event_sources_for_event(self, state, player, event, *, timing=None):
        """Resolve all registered sources subscribed to an event.

        Event subscriptions are queried from the registry rather than from a
        card-specific list.  This is the common path for native and Heimer
        copies, including replacement effects; adding a new registered source
        therefore does not require another branch in cleanup or trigger code.
        """
        sources = []
        for spec in self.abilities.for_event(event, timing=timing):
            sources.extend(self._registry_event_sources(state, player, spec.ability_id))
        return sources

    def _resolve_registry_copy(self, state, player, args, rng, target=None):
        """Resolve a Heimer copied ability through its registered action kind."""
        spec = self.abilities.get(args["ability_id"])
        source = self._unit(state, args["source"])
        if source is None or source["owner"] != player or source["code"] != "OGN-111" or source["exhausted"]:
            raise ValueError("copied ability source is unavailable")
        if not spec.requires_exhaust or not spec.copyable:
            raise ValueError("ability is not copyable by Heimerdinger")
        accelerate_window = (state.get("phase") == "decision"
                             and (state.get("decision") or {}).get("accelerate"))
        if spec.timing == "reaction" and state.get("phase") not in {"chain", "showdown"} \
                and not accelerate_window:
            raise ValueError("copied Reaction ability is unavailable outside a reaction window")
        row = state["players"][player]
        if (spec.action_kind == "legend_energy"
                and (row["legend"] != "OGN-253" or row["legend_exhausted"]
                     or not self._played_for_legion(state, player))):
            raise ValueError("copied Hand of Noxus Legion ability is unavailable")
        action = spec.action_kind
        # Every copied ability exhausts the activating Heimer exactly once.
        source["exhausted"] = True
        if action == "unit_caitlyn":
            target_unit = self._unit(state, target)
            if target_unit is None or not self._is_field(state, target_unit["location"]):
                raise ValueError("Caitlyn copied ability requires a battlefield unit")
            self._deal_damage(state, target_unit, self.might(state, source))
            self._cleanup(state, rng)
        elif action == "unit_malzahar":
            target_unit = self._unit(state, target)
            if target_unit is not None:
                if target_unit["owner"] != player:
                    raise ValueError("Malzahar copied ability requires a friendly unit")
                state["units"].remove(target_unit)
                self._trash_unit_card(state, target_unit)
            else:
                gear = next((g for g in row["gear"] if g["id"] == target), None)
                if gear is None:
                    raise ValueError("Malzahar copied ability target unavailable")
                row["gear"].remove(gear)
                self._trash_gear_card(state, gear)
            row["power"].extend(["spell_any", "spell_any"])
        elif action == "unit_buff":
            source["buff"] += 1
        elif action == "legend_energy":
            if (row["legend"] != "OGN-253" or row["legend_exhausted"]
                    or not self._played_for_legion(state, player)):
                raise ValueError("copied Hand of Noxus Legion ability is unavailable")
            row["energy"] += 1
        elif action == "legend_spell_power":
            row["power"].append("spell_any")
        elif action == "legend_recruit":
            if row["energy"] < 1:
                raise ValueError("copied recruit requires energy")
            row["energy"] -= 1
            self._new_unit(state, TOKEN, player, f"base:{player}")
        elif action == "legend_channel":
            if not row["rune_deck"]:
                raise ValueError("copied channel requires a rune deck")
            rune = {**row["rune_deck"].pop(0), "exhausted": True}
            row["runes"].append(rune)
        elif action == "legend_buff":
            if row["energy"] < 1:
                raise ValueError("copied buff requires energy")
            unit = self._unit(state, target)
            if unit is None or unit["owner"] != player:
                raise ValueError("copied buff target unavailable")
            row["energy"] -= 1
            self._apply_buff(state, unit)
        elif action == "legend_ganking":
            unit = self._unit(state, target)
            if unit is None or unit["owner"] != player:
                raise ValueError("copied Ganking target unavailable")
            unit["temporary_ganking"] = True
        elif action == "legend_move":
            if row["energy"] < 2:
                raise ValueError("copied move requires energy")
            unit = self._unit(state, target)
            if unit is None or unit["owner"] != player:
                raise ValueError("copied move target unavailable")
            row["energy"] -= 2
            state["decision"] = {"kind": "choice", "player": player,
                                  "options": [f"base:{player}", *range(len(state["fields"]))],
                                  "item": {"registry_copy": True, "ability_id": spec.ability_id,
                                           "source": source["id"], "target": unit["id"], "owner": player},
                                  "destination_choice": True}
            source["registry_pending_exhausted"] = True
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return
        elif action == "legend_teemo":
            if row["energy"] < 1:
                raise ValueError("copied Swift Scout requires energy")
            if target in row["champion"]:
                row["champion"].remove(target)
                row["hand"].append(target)
            else:
                unit = self._unit(state, target)
                if unit is None or unit["owner"] != player or unit["code"] != "OGN-121":
                    raise ValueError("copied Swift Scout requires Teemo")
                state["units"].remove(unit)
                self._hand_unit_card(state, unit)
            row["energy"] -= 1
        elif action == "gear_resource":
            cost = dict(spec.cost)
            if "energy" in cost:
                row["energy"] += int(cost["energy"])
            else:
                resource = cost.get("resource")
                if resource is None:
                    raise ValueError("copied Gear resource has no domain or energy")
                row["power"].append(resource)
        elif action == "gear_damage":
            unit = self._unit(state, target)
            if unit is None or not self._is_field(state, unit["location"]):
                raise ValueError("copied Iron Ballista target unavailable")
            self._deal_damage(state, unit, 2)
            self._cleanup(state, rng)
        elif action == "gear_return":
            row = state["players"][player]
            unit = self._unit(state, target)
            if unit is not None:
                if unit["id"] == source["id"] or unit["owner"] != player:
                    raise ValueError("copied Pack of Wonders target unavailable")
                state["units"].remove(unit)
                self._hand_unit_card(state, unit)
            else:
                gear = next((g for g in row["gear"] if g["id"] == target), None)
                if gear is not None:
                    row["gear"].remove(gear)
                    self._hand_gear_card(state, gear)
                else:
                    hidden = next((h for h in row.get("hidden", []) if h["id"] == target), None)
                    if hidden is None:
                        raise ValueError("copied Pack of Wonders target unavailable")
                    row["hidden"].remove(hidden)
                    row["hand"].append(hidden["card"])
        elif action == "gear_debuff":
            unit = self._unit(state, target)
            if unit is None:
                raise ValueError("copied Gear debuff target unavailable")
            unit["temporary"] -= 1
        elif action == "gear_buff_exhausted":
            unit = self._unit(state, target)
            if unit is None or unit["owner"] != player or not unit["exhausted"]:
                raise ValueError("copied Gear buff target unavailable")
            self._apply_buff(state, unit)
        elif action == "gear_move":
            unit = self._unit(state, target)
            if unit is None or unit["owner"] != player or not self._is_field(state, unit["location"]):
                raise ValueError("copied Gear move target unavailable")
            self._resolve_move(state, [unit], f"base:{player}", player, rng, from_effect=True)
        elif action == "gear_ready_next":
            row["ready_play"] = True
        elif action == "gear_tome":
            row["spell_bonus_damage"] = row.get("spell_bonus_damage", 0) + 1
        elif action == "gear_kill":
            # A copied self-referencing Gear ability applies to the activating
            # source (Heimer) and therefore kills it after granting its effect.
            row["energy"] += 0
            source["damage"] = self.might(state, source)
            self._cleanup(state, rng)
        elif action == "gear_grab":
            if row["energy"] < 1 or len(row["trash"]) < 3:
                raise ValueError("copied Garbage Grabber cost unavailable")
            row["energy"] -= 1
            self._recycle_cards_to_main(state, player, list(row["trash"][:3]), source="trash", rng=rng)
            self._draw(state, player, 1, rng)
        elif action == "gear_armory_protect":
            if not row["hand"]:
                raise ValueError("copied Armory requires a discard")
            discarded = row["hand"].pop(0)
            row["trash"].append(discarded)
            target_unit = self._unit(state, target)
            if target_unit is None or target_unit["owner"] != player:
                raise ValueError("copied Armory target unavailable")
            target_unit["death_replacement"] = {"kind": "armory", "turn": state["turn"]}
        elif action == "gear_baited_hook":
            if row["energy"] < 1 or "order" not in row["power"]:
                raise ValueError("copied Baited Hook cost unavailable")
            target_unit = self._unit(state, target)
            if target_unit is None or target_unit["owner"] != player:
                raise ValueError("copied Baited Hook target unavailable")
            row["energy"] -= 1
            row["power"].remove("order")
            killed_might = self.might(state, target_unit)
            target_unit["damage"] = killed_might
            self._cleanup(state, rng)
            top = list(row["main"][:5])
            choices = [uid for uid in top
                       if self.cards[state["cards"][uid]["code"]]["type"] == "unit"
                       and self.cards[state["cards"][uid]["code"]]["might"] <= killed_might + 1]
            self._open_reveal(state, owner=player, cards=top, mode="select", chooser=player,
                              minimum=0, maximum=1, effect="baited_hook", choices=choices,
                              item={"effect": "gear_baited_hook", "owner": player,
                                    "target": target, "copied_source": source["id"]}, rng=rng)
        elif action == "gear_forge_recycle":
            cards = [uid for owner in state["players"] for uid in owner["trash"]]
            self._open_reveal(state, owner=player, cards=cards, mode="select", chooser=player,
                              minimum=0, maximum=min(4, len(cards)), effect="forge_recycle", choices=cards, rng=rng)
        else:
            raise ValueError(f"copied ability handler is not implemented: {spec.ability_id}")
        state["passes"] = 0

    def _gear_actions(self, state):
        """Play supported gear to the controller's Base and expose simple abilities."""
        player = state["actor"]
        row = state["players"][player]
        result = []
        if state["phase"] == "main" and not self._cards_locked(state, player):
            for card in row["hand"]:
                code = state["cards"][card]["code"]
                if not (code in GEAR_CODES or self._is_executable_kind(code, "gear")):
                    continue
                data = self.cards[code]
                for payment in self._payments(state, player, data["energy"], data["domains"],
                                               data["power_cost"] or 0):
                    result.append(Action.make("play_gear", card=card, payment=payment))
        gear_resource = {"OGN-040": "fury", "OGN-081": "calm", "OGN-120": "mind",
                         "OGN-163": "body", "OGN-204": "chaos", "OGN-245": "order"}
        for gear in row["gear"]:
            if gear["exhausted"]:
                continue
            behavior = self._behavior_code(gear["code"])
            implementation = self._card_implementation(gear["code"])
            activated = implementation.activated_effect if implementation else None
            gear_resource_codes = {"OGN-040", "OGN-081", "OGN-120", "OGN-163",
                                   "OGN-204", "OGN-245", "OGN-098"}
            if (state["phase"] not in {"main", "decision"}
                    and gear["code"] not in gear_resource_codes
                    and behavior not in gear_resource
                    and activated not in {"gear_energy_from_rainbow", "gear_rainbow_from_energy"}):
                continue
            if activated == "gear_draw":
                for payment in self._payments(state, player, 1, ["calm"], 0):
                    result.append(Action.make("gear_activate", gear=gear["id"],
                                              effect=activated, payment=payment))
            elif activated == "gear_energy_from_rainbow":
                for amount in range(1, row["power"].count("any") + 1):
                    result.append(Action.make("gear_activate", gear=gear["id"],
                                              effect=activated, amount=amount))
            elif activated == "gear_rainbow_from_energy":
                for amount in range(1, row["energy"] + 1):
                    result.append(Action.make("gear_activate", gear=gear["id"],
                                              effect=activated, amount=amount))
            elif activated == "gear_buff_three":
                candidates = [u["id"] for u in state["units"]]
                if candidates:
                    result.append(Action.make("gear_targeted", gear=gear["id"],
                                              effect=activated,
                                              target_candidates=candidates))
                    result.extend(Action.make("gear_target", gear=gear["id"],
                                              effect=activated, target=u["id"])
                                  for u in state["units"])
            elif activated == "play_three_recruit":
                locations = [f"base:{player}"] + [i for i, field in enumerate(state["fields"])
                             if field["controller"] == player]
                if locations:
                    result.append(Action.make("gear_tokens", gear=gear["id"],
                                              token="recruit", count=3,
                                              locations=locations))
            if behavior in gear_resource:
                result.append(Action.make("gear_resource", gear=gear["id"], domain=gear_resource[behavior]))
            elif gear["code"] == "OGN-098":
                result.append(Action.make("gear_resource", gear=gear["id"], energy=1))
            elif gear["code"] == "OGN-017":
                candidates = [u["id"] for u in state["units"] if self._is_field(state, u["location"])]
                if candidates:
                    result.append(Action.make("gear_targeted", gear=gear["id"], effect="gear_damage",
                                              target_candidates=candidates))
                result.extend(Action.make("gear_target", gear=gear["id"], effect="gear_damage", target=u["id"])
                               for u in state["units"] if self._is_field(state, u["location"]))
            elif gear["code"] == "OGN-181":
                candidates = ([u["id"] for u in self._units(state, player)]
                              + [g["id"] for g in row["gear"] if g["id"] != gear["id"]]
                              + [h["id"] for h in row.get("hidden", [])])
                if candidates:
                    result.append(Action.make("gear_targeted", gear=gear["id"], effect="gear_return",
                                              target_candidates=candidates))
                result.extend(Action.make("gear_target", gear=gear["id"], effect="gear_return", target=u["id"])
                              for u in self._units(state, player))
                result.extend(Action.make("gear_target", gear=gear["id"], effect="gear_return", target=g["id"])
                              for g in row["gear"] if g["id"] != gear["id"])
                result.extend(Action.make("gear_target", gear=gear["id"], effect="gear_return", target=h["id"])
                              for h in row.get("hidden", []))
            elif gear["code"] == "OGN-090":
                candidates = [u["id"] for u in self._units(state)]
                if candidates:
                    result.append(Action.make("gear_targeted", gear=gear["id"], effect="gear_debuff",
                                              target_candidates=candidates))
                result.extend(Action.make("gear_target", gear=gear["id"], effect="gear_debuff", target=u["id"])
                               for u in self._units(state))
            elif gear["code"] == "OGN-124":
                candidates = [u["id"] for u in self._units(state, player) if u["exhausted"]]
                if candidates:
                    result.append(Action.make("gear_targeted", gear=gear["id"], effect="gear_buff_exhausted",
                                              target_candidates=candidates))
                result.extend(Action.make("gear_target", gear=gear["id"], effect="gear_buff_exhausted", target=u["id"])
                               for u in self._units(state, player) if u["exhausted"])
            elif gear["code"] == "OGN-184":
                candidates = [u["id"] for u in self._units(state, player)
                              if self._is_field(state, u["location"])]
                if candidates:
                    result.append(Action.make("gear_targeted", gear=gear["id"], effect="gear_move",
                                              target_candidates=candidates))
                result.extend(Action.make("gear_target", gear=gear["id"], effect="gear_move", target=u["id"])
                               for u in self._units(state, player) if self._is_field(state, u["location"]))
            elif gear["code"] == "OGN-021":
                result.append(Action.make("gear_ready_next", gear=gear["id"]))
            elif gear["code"] == "OGN-032":
                result.append(Action.make("gear_tome", gear=gear["id"]))
            elif gear["code"] == "OGN-186":
                result.append(Action.make("gear_kill", gear=gear["id"]))
            elif gear["code"] == "OGN-099" and row["energy"] >= 1 and len(row["trash"]) >= 3:
                result.append(Action.make("gear_grab", gear=gear["id"]))
            elif gear["code"] == "OGN-212":
                result.append(Action.make("gear_forge_recycle", gear=gear["id"]))
            elif gear["code"] == "OGN-023" and row["hand"]:
                candidates = [u["id"] for u in self._units(state, player)]
                if candidates:
                    result.append(Action.make("gear_targeted", gear=gear["id"], effect="gear_armory_protect",
                                              target_candidates=candidates))
                    result.extend(Action.make("gear_target", gear=gear["id"], effect="gear_armory_protect",
                                               target=u["id"]) for u in self._units(state, player))
            elif gear["code"] == "OGN-242" and row["energy"] >= 1 and "order" in row["power"]:
                candidates = [u["id"] for u in self._units(state, player)]
                if candidates:
                    result.append(Action.make("gear_targeted", gear=gear["id"], effect="gear_baited_hook",
                                              target_candidates=candidates))
                    result.extend(Action.make("gear_target", gear=gear["id"], effect="gear_baited_hook",
                                               target=u["id"]) for u in self._units(state, player))
        return result

    def _resource_actions(self, state):
        player = state["actor"]
        row = state["players"][player]
        result = []
        for rune in row["runes"]:
            if not rune["exhausted"]:
                result.append(Action.make("exhaust_rune", rune=rune["id"]))
            result.append(Action.make("recycle_rune", rune=rune["id"]))
        if state.get("rune_undo") and state["phase"] == "main":
            result.append(Action.make("undo_rune"))
        for unit in self._units(state, player):
            implementation = self._card_implementation(unit["code"])
            if (implementation and implementation.activated_effect == "spend_buff_four"
                    and not unit["exhausted"] and unit.get("buff", 0) > 0):
                result.append(Action.make("unit_registry_ability", unit=unit["id"],
                                          effect=implementation.activated_effect))
            if unit["code"] == "OGN-078" and not unit["exhausted"]:
                result.append(Action.make("unit_buff", unit=unit["id"]))
            if unit["code"] == "OGN-036" and not unit["exhausted"] and row["trash"]:
                result.append(Action.make("unit_recycle_buff", unit=unit["id"]))
            if (unit["code"] == "OGN-068" and not unit["exhausted"]
                    and self._is_field(state, unit["location"])):
                result.append(Action.make("unit_ability_targeted", ability="caitlyn", unit=unit["id"],
                                          target_candidates=[target["id"] for target in state["units"]
                                                             if self._is_field(state, target["location"])]))
                result.extend(Action.make("unit_caitlyn", unit=unit["id"], target=target["id"])
                              for target in state["units"] if self._is_field(state, target["location"]))
            if unit["code"] == "OGN-113" and not unit["exhausted"]:
                result.append(Action.make("unit_ability_targeted", ability="malzahar", unit=unit["id"],
                                          target_candidates=[target["id"] for target in self._units(state, player)]
                                          + [gear["id"] for gear in row["gear"]]))
                result.extend(Action.make("unit_malzahar", unit=unit["id"], target=target["id"])
                              for target in self._units(state, player))
                result.extend(Action.make("unit_malzahar", unit=unit["id"], target=gear["id"])
                              for gear in row["gear"])
            if unit["code"] == "OGN-157" and not unit["exhausted"] and unit["buff"]:
                options = [option for option in ("damage", "stun", "ready", "ganking")
                           if option not in unit.get("udyr_choices", [])]
                if options:
                    result.append(Action.make("unit_udyr", unit=unit["id"], options=options))
            if unit["code"] == "OGN-111" and not unit["exhausted"]:
                # Heimer's copied abilities are discovered from the declarative
                # registry.  This deliberately excludes non-E abilities such
                # as Vi/Udyr and automatically picks up future registrations.
                result.extend(self._heimer_registry_actions(state, player, unit))
        legend_implementation = self._card_implementation(row["legend"])
        if (legend_implementation is not None
                and legend_implementation.activated_effect == "legend_rainbow"
                and not row["legend_exhausted"]
                and (state["phase"] in {"chain", "showdown"}
                     or ((state.get("decision") or {}).get("accelerate")
                         and state["phase"] == "decision"))):
            result.append(Action.make("legend_rainbow"))
        # During an Accelerate payment window the unit is represented on the
        # Board but its play process has not completed.  The shared finalized
        # count therefore excludes it automatically.
        played_for_legion = self._played_for_legion(state, player)
        if row["legend"] == "OGN-253" and not row["legend_exhausted"] and played_for_legion:
            result.append(Action.make("legend_energy"))
        if row["legend"] == "OGN-247" and not row["legend_exhausted"]:
            result.append(Action.make("legend_spell_power"))
        if (row["legend"] == "OGN-265" and state["phase"] == "main"
                and not row["legend_exhausted"] and row["energy"] >= 1):
            result.append(Action.make("legend_recruit"))
        if (row["legend"] == "OGN-249" and state["phase"] == "main"
                and not row["legend_exhausted"] and row["rune_deck"]
                and any(option["owner"] == player for option in state.get("legend_options", []))):
            result.append(Action.make("legend_channel"))
        if row["legend"] == "OGN-257" and state["phase"] == "main" and not row["legend_exhausted"] and row["energy"] >= 1:
            candidates = [u["id"] for u in self._units(state, player)]
            if candidates:
                result.append(Action.make("legend_targeted", ability="buff", target_candidates=candidates))
            result.extend(Action.make("legend_buff", target=u["id"]) for u in self._units(state, player))
        if row["legend"] == "OGN-259" and state["phase"] == "main" and not row["legend_exhausted"] and row["energy"] >= 2:
            candidates = [u["id"] for u in self._units(state, player)]
            if candidates:
                result.append(Action.make("legend_move_targeted", target_candidates=candidates))
            for unit in self._units(state, player):
                for destination in (f"base:{player}", *range(len(state["fields"]))):
                    if destination != unit["location"]:
                        result.append(Action.make("legend_move", target=unit["id"], destination=destination))
        if row["legend"] == "OGN-267" and state["phase"] == "main" and not row["legend_exhausted"]:
            candidates = [u["id"] for u in self._units(state, player)]
            if candidates:
                result.append(Action.make("legend_targeted", ability="ganking", target_candidates=candidates))
            result.extend(Action.make("legend_ganking", target=u["id"]) for u in self._units(state, player))
        if row["legend"] == "OGN-263" and state["phase"] == "main" \
                and not row["legend_exhausted"] and row["energy"] >= 1:
            candidates = list(row["champion"]) + [u["id"] for u in self._units(state, player)
                                                     if u["code"] == "OGN-121"]
            if candidates:
                result.append(Action.make("legend_targeted", ability="teemo", target_candidates=candidates))
            result.extend(Action.make("legend_teemo", target=card)
                           for card in row["champion"]
                           if state["cards"][card]["code"] == "OGN-121")
            result.extend(Action.make("legend_teemo", target=u["id"])
                           for u in self._units(state, player)
                           if u["code"] == "OGN-121")
        return result

    def _mark_play_finalized(self, state, player, card=None, *, item=None,
                             trigger_sink=None, rng=None):
        """Record a completed card-play process exactly once.

        ``played`` remains the public compatibility alias for the finalized
        count.  Rules that ask whether another card was played this turn
        must read this finalized marker instead (RUP5 350.1, 352.2, 420.4.b,
        812.1.c).  A chain item or direct play context may be revisited by a
        reveal/continuation, so the marker is deliberately idempotent.
        """
        if item is not None:
            if item.get("finalized_play_marked"):
                return False
            item["finalized_play_marked"] = True
            player = item.get("played_by", player)
            item["finalized_by"] = player
        if card is None:
            return False
        row = state["players"][player]
        # Older saved states do not have the new fields.  Initialise them on
        # first use so loading a replay remains compatible.
        row.setdefault("finalized_played", row.get("played", 0))
        row.setdefault("finalized_cards", [])
        # ``played`` now represents finalized cards as well.  Keeping the
        # legacy field synchronized avoids breaking saved states and GUI
        # consumers while removing its old provisional semantics.
        if row["finalized_played"] < row.get("played", 0):
            row["finalized_played"] = row["played"]
        row["finalized_played"] += 1
        row["played"] = row["finalized_played"]
        row["finalized_cards"].append(card)
        # Yordle Explorer listens to the finalized play event, rather than a
        # provisional hand/Chain insertion.  That keeps ordinary, targeted,
        # Hidden, and nested free plays on the same event path.  The Explorer
        # itself is excluded from its own play event because its trigger was
        # not active before that card entered play.
        played_data = state.get("cards", {}).get(card, {})
        played_rules = self.cards.get(played_data.get("code"), {})
        if (played_rules.get("power_cost") is not None
                and played_rules.get("power_cost", 0) >= 2):
            yordle_sources = []
            for source in self._units(state, player):
                implementation = self._card_implementation(source["code"])
                if (implementation is not None
                        and implementation.global_effect == "draw_on_power_two"
                        and source.get("card") != card):
                    yordle_sources.append(source["id"])
            if item is not None:
                item.setdefault("post_triggers", []).extend(
                    {"effect": "yordle_explorer", "source": source_id,
                     "owner": player}
                    for source_id in yordle_sources)
            elif trigger_sink is not None:
                trigger_sink.extend(
                    {"effect": "yordle_explorer", "source": source_id,
                     "owner": player}
                    for source_id in yordle_sources)
            else:
                for _ in yordle_sources:
                    self._draw(state, player, 1,
                               rng if rng is not None else random.Random(0))
        return True

    def _spell_post_triggers(self, state, player, second_card):
        """Build post-resolution triggers for a finalized spell play.

        The trigger list is attached when the spell becomes a Chain item, but
        each effect is generated only after that item resolves.  Keeping this
        in one helper makes ordinary, targeted, field-targeted, and Counter
        spells follow the same extension point.
        """
        triggers = [{"effect": "ravenbloom", "owner": player}]
        if second_card:
            triggers.append({"effect": "darius", "owner": player})
        if state["turn_player"] != player:
            triggers.extend(
                {"effect": "viktor_innovator", "source": source["id"], "owner": player}
                for source in self._units(state, player) if source["code"] == "OGN-117"
            )
        return triggers

    def _played_for_legion(self, state, player):
        """Return the number of this player's finalized cards this turn.

        ``played`` remains a synchronized compatibility alias for this count;
        older hand-built/replay states that lack ``finalized_played`` are read
        through the same value.  The live Accelerate card is not counted until
        its payment and entry process is complete.
        """
        row = state["players"][player]
        # ``played`` is kept as a synchronized public alias.  Taking the
        # maximum also migrates older hand-built/replay states that only set
        # that field, while the live Accelerate card no longer increments it
        # until finalization, so a pending first card still returns zero.
        return max(int(row.get("finalized_played", 0)), int(row.get("played", 0)))

    def _accelerate_resource_actions(self, state, player):
        """Resource Add abilities legal while paying an Accelerate cost.

        RUP5 357.1.a/430.3 permits Reaction resource abilities during a cost
        payment. These actions stay inside the pending decision; they do not
        open priority and do not resolve the unit entry prematurely.
        """
        actions = []
        for action in self._resource_actions(state) + self._gear_actions(state):
            if action.kind in {"legend_energy", "legend_rainbow", "gear_resource"}:
                actions.append(action)
                continue
            if action.kind == "ability_activate":
                args = json.loads(action.arguments)
                try:
                    spec = self.abilities.get(args.get("ability_id"))
                except KeyError:
                    continue
                if spec.action_kind in {"legend_energy", "gear_resource"}:
                    actions.append(action)
        return actions

    def _payments(self, state, player, energy, domains, power_count, any_count=0, *, spell=False):
        row = state["players"][player]
        if row["energy"] < energy:
            return []
        result = []
        for chosen in combinations(range(len(row["power"])), power_count+any_count):
            # All colored costs of supported spells use the same card domain.
            if sum(row["power"][i] in domains or row["power"][i] == "any"
                   or (spell and row["power"][i] == "spell_any") for i in chosen) >= power_count:
                result.append(list(chosen))
        return result

    def _spell_actions(self, state):
        player = state["actor"]
        row = state["players"][player]
        result = []
        if self._cards_locked(state, player):
            return result
        for card in row["hand"]:
            code = state["cards"][card]["code"]
            if (not (code in SPELL_CODES or self._is_executable_kind(code, "spell"))
                    or (state["phase"] == "chain" and not self._is_reaction_code(code))):
                continue
            if code == "OGN-008" and not row["hand"]:
                continue
            data = self.cards[code]
            implementation = self._card_implementation(code)
            if implementation and implementation.counter_scope == "friendly_target":
                counter_targets = [f"chain:{index}" for index, item in enumerate(state.get("chain", []))
                                   if self._chain_item_chooses_friendly_target(state, item, player)]
                if counter_targets:
                    for payment in self._payments(state, player, data["energy"], data["domains"],
                                                  data["power_cost"] or 0):
                        result.append(Action.make("play_counter", card=card, payment=payment,
                                                  targets=counter_targets))
                continue
            if implementation and implementation.spell_effect:
                spell_energy = max(0, data["energy"] - row.get("spell_discount", 0))
                if (implementation.cost_reduction_effect == "control_mech"
                        and any(unit["owner"] == player
                                and "Mech" in self.cards.get(unit["code"], {}).get("tags", [])
                                for unit in state["units"])):
                    spell_energy = max(0, spell_energy - 2)
                for payment in self._payments(state, player, spell_energy, data["domains"],
                                              data["power_cost"] or 0, spell=True):
                    if implementation.target_scope:
                        candidates = self._registry_spell_target_candidates(
                            state, player, implementation.target_scope)
                        if not candidates:
                            continue
                        result.append(Action.make(
                            "play_spell_targeted", card=card,
                            target_candidates=candidates,
                            target_min=implementation.target_min,
                            target_max=implementation.target_max,
                            allow_repeat=False, target_pairs=None,
                            ordered_pairs=False, destination=None,
                            destination_select=False, spend_buff=None,
                            payment=payment, registry_targeted=True))
                    else:
                        result.append(Action.make("play_spell", card=card, targets=[],
                                                  destination=None, spend_buff=None,
                                                  payment=payment))
                continue
            targeted_only = code in {"OGN-029", "OGN-104", "OGN-183", "OGN-248"}
            if code in {"OGN-045", "OGN-064", "OGN-080"}:
                if state.get("chain"):
                    counter_targets = []
                    for index, target in enumerate(state["chain"]):
                        if target.get("effect") != "spell":
                            continue
                        target_data = self.cards.get(target.get("code"), {})
                        if code == "OGN-045" and (target_data.get("energy", 99) > 4
                                                    or target_data.get("power_cost", 99) > 1):
                            continue
                        counter_targets.append(f"chain:{index}")
                    if counter_targets:
                        for payment in self._payments(state, player, data["energy"], data["domains"], data["power_cost"]):
                            result.append(Action.make("play_counter", card=card, payment=payment,
                                                      targets=counter_targets))
                continue
            if code in FIELD_TARGET_SPELLS or code == "OGN-268":
                energy = max(0, data["energy"] - row.get("spell_discount", 0))
                for payment in self._payments(state, player, energy, data["domains"], data["power_cost"], spell=True):
                    result.append(Action.make("play_field_targeted", card=card,
                                              fields=list(range(len(state["fields"]))),
                                              x_choice=code == "OGN-268", payment=payment))
            if code in {"OGN-022", "OGN-025", "OGN-047", "OGN-062", "OGN-083", "OGN-114", "OGN-115", "OGN-122", "OGN-123", "OGN-129", "OGN-133", "OGN-134", "OGN-138", "OGN-144", "OGN-145", "OGN-153", "OGN-071", "OGN-156", "OGN-170", "OGN-179", "OGN-183", "OGN-187", "OGN-237", "OGN-198", "OGN-221", "OGN-224", "OGN-233", "OGN-244"}:
                targets = [[]]
            elif code == "OGN-008":
                targets = [[u["id"]] for u in state["units"] if self._is_field(state, u["location"])]
            elif code == "OGN-057":
                targets = [[u["id"]] for u in state["units"] if self._is_field(state, u["location"])]
            elif code == "OGN-102":
                targets = [[u["id"]] for u in self._units(state, player)]
            elif code == "OGN-033":
                targets = [[u["id"]] for u in self._units(state, 1 - player)]
            elif code == "OGN-048":
                targets = [[]] + [[u["id"]] for u in self._units(state, player) if not u["exhausted"]]
            elif code in {"OGN-128", "OGN-209"}:
                targets = [[friendly["id"], enemy["id"]]
                           for friendly in self._units(state, player)
                           for enemy in self._units(state, 1-player)]
            elif code == "OGN-108":
                targets = [[first["id"], second["id"]]
                           for first in self._units(state, player)
                           for second in self._units(state, player)
                           if first["id"] != second["id"]]
            elif code == "OGN-260":
                targets = [[friendly["id"], enemy["id"]]
                           for friendly in self._units(state, player)
                           for enemy in self._units(state, 1-player)
                           if self._is_field(state, enemy["location"])]
            elif code == "OGN-266":
                targets = [[u["id"]] for u in state["units"] if self._is_field(state, u["location"])]
            elif code == "OGN-250":
                targets = [[u["id"]] for u in self._units(state, player, f"base:{player}")]
            elif code == "OGN-270":
                targets = [[u["id"]] for u in self._units(state, player, f"base:{player}")]
            elif code in {"OGN-043", "OGN-203"}:
                targets = [[u["id"]] for u in self._units(state, 1-player)
                           if code != "OGN-203" or self._is_field(state, u["location"])]
            elif code == "OGN-173":
                targets = [[u["id"]] for u in self._units(state, player)]
            elif code in {"OGN-168", "OGN-180"}:
                targets = [[u["id"]] for u in state["units"]
                           if self._is_field(state, u["location"])]
                if code == "OGN-180":
                    targets.extend([[gear["id"]] for owner_row in state["players"]
                                    for gear in owner_row["gear"]])
            elif code in {"OGN-053", "OGN-069", "OGN-104", "OGN-146"}:
                targets = [[u["id"]] for u in self._units(state, player)]
            elif code == "OGN-252":
                targets = [[u["id"]] for u in state["units"]]
            elif code == "OGN-262":
                targets = [[u["id"]] for u in state["units"]
                           if u["owner"] != player and self._is_field(state, u["location"])]
            elif code in {"OGN-169", "OGN-172", "OGN-213"}:
                targets = [[u["id"]] for u in state["units"] if self._is_field(state, u["location"])
                           and (code != "OGN-169" or self.might(state, u) <= 3)]
            elif code == "OGN-248":
                targets = [[]]
            elif code == "OGN-256":
                # Fox-Fire may kill any number of units at one battlefield,
                # provided their current Might totals no more than four.
                targets = [[]]
                for field in range(len(state["fields"])):
                    field_units = list(self._units(state, location=field))
                    for count in range(1, len(field_units) + 1):
                        targets.extend(list(combo) for combo in combinations(
                            [u["id"] for u in field_units], count)
                            if sum(self.might(state, self._unit(state, uid)) for uid in combo) <= 4)
            elif code == "OGN-220":
                targets = [[friendly["id"], enemy["id"]]
                           for friendly in self._units(state, player)
                           if self._is_field(state, friendly["location"])
                           for enemy in self._units(state, 1-player, friendly["location"])]
            elif code == "OGN-105":
                all_units = [u["id"] for u in state["units"]]
                targets = [[]] + [[uid] for uid in all_units]
                targets += [list(pair) for pair in combinations(all_units, 2)]
            elif code == "OGN-029":
                targets = [[a, b] for a in [u["id"] for u in state["units"]]
                           for b in [u["id"] for u in state["units"]]]
            elif code == "OGN-206":
                targets = [list(pair) for pair in combinations([u["id"] for u in self._units(state, player)], 2)]
            elif code == "OGN-258":
                targets = [[u["id"]] for u in self._units(state, 1 - player)]
            elif code == "OGN-046":
                targets = [[u["id"]] for u in self._units(state, player)]
            elif code in {"OGN-014"}:
                targets = [[u["id"]] for u in state["units"] if self._is_field(state, u["location"])]
            else:
                targets = [[u["id"]] for u in state["units"]
                           if code not in {"OGN-005", "OGN-009", "OGN-014", "OGN-024", "OGN-085", "OGN-105"}
                           or self._is_field(state, u["location"])]
            spec = self._spell_target_spec(state, player, code)
            if (spec is not None and spec.get("kind") != "field"
                    and not spec.get("candidates") and int(spec.get("min", 1)) > 0):
                # Required target spells are unavailable when no legal target
                # exists; do not expose a legacy action that would only fizzle
                # or leave an interactive target window with zero choices.
                continue
            if code == "OGN-268":
                # Keep the expanded form for non-GUI policies and replay
                # compatibility; the GUI prefers play_field_targeted.
                for destination in range(len(state["fields"])):
                    for x in range(len(row["power"]) + 1):
                        if row["energy"] < data["energy"]:
                            continue
                        payment = list(range(x))
                        result.append(Action.make("play_spell", card=card, targets=[],
                                                  destination=destination, x=x, spend_buff=None,
                                                  payment=payment))
                continue
            buffs = [None]
            if code in {"OGN-146", "OGN-207"}:
                buffs += [u["id"] for u in self._units(state, player) if u["buff"]]
            targeted_added = False
            for selected in targets:
                destinations = [None]
                if code in {"OGN-043", "OGN-173", "OGN-250", "OGN-270", "OGN-258"}:
                    unit = self._unit(state, selected[0])
                    destinations = [f"base:{unit['owner']}", *range(len(state["fields"]))]
                    destinations = [destination for destination in destinations
                                    if destination != unit["location"]]
                deflect = sum(self._deflect(state, target) for uid in selected
                              for target in [self._unit(state, uid)]
                              if target is not None and target["owner"] != player)
                for destination in destinations:
                    for spend in buffs:
                        energy = 0 if spend is not None else data["energy"]
                        if spend is None and row.get("spell_discount", 0):
                            energy = max(0, energy - row["spell_discount"])
                        if code == "OGN-014" and spend is None:
                            highest = max((self.might(state, u) for u in self._units(state, player)), default=0)
                            energy = max(0, energy - highest)
                        if code == "OGN-047" and spend is None:
                            if state["victory"] - state["points"][1-player] <= 3:
                                energy = max(0, energy - 2)
                        if spend is None and energy > 0 and any(
                                unit["owner"] == player and unit["code"] == "OGN-084"
                                and self._is_field(state, unit["location"])
                                for unit in state["units"]):
                            energy = max(1, energy - 1)
                        power = 0 if spend is not None else data["power_cost"]
                        for payment in self._payments(state, player, energy, data["domains"], power, deflect,
                                                      spell=True):
                            if not targeted_only:
                                result.append(Action.make("play_spell", card=card, targets=selected,
                                                          destination=destination, spend_buff=spend, payment=payment))
                            # Offer a UI-driven target window alongside the legacy
                            # fully-expanded actions.  Existing agents remain
                            # compatible while interactive clients can select and
                            # confirm targets one at a time.
                            if (code in (SIMPLE_TARGET_SPELLS | PAIR_TARGET_SPELLS |
                                         DESTINATION_TARGET_SPELLS | OPTIONAL_TARGET_SPELLS |
                                         CONSTRAINED_MULTI_TARGET_SPELLS |
                                         {"OGN-029", "OGN-104", "OGN-105", "OGN-183",
                                          "OGN-206", "OGN-248"}) and not targeted_added):
                                spec = self._spell_target_spec(state, player, code)
                                if spec is None or spec.get("kind") == "field":
                                    continue
                                spec = dict(spec)
                                spec["candidates"] = [uid for uid in spec.get("candidates", [])
                                                      if self._is_targetable(state, player, uid)]
                                if spec.get("target_pairs") is not None:
                                    spec["target_pairs"] = [pair for pair in spec["target_pairs"]
                                                             if all(self._is_targetable(state, player, uid)
                                                                    for uid in pair)]
                                candidates = list(spec.get("candidates", []))
                                target_count = int(spec.get("min", 1))
                                target_pairs = [list(pair) for pair in spec.get("target_pairs", [])]
                                target_min = (0 if code in (OPTIONAL_TARGET_SPELLS | CONSTRAINED_MULTI_TARGET_SPELLS)
                                              else target_count if code != "OGN-105" else 0)
                                target_max = int(spec.get("max", target_count))
                                # Do not expose a targeted play transaction
                                # when the mandatory target shape has no legal
                                # candidates.  Otherwise the card enters a
                                # dead target decision with zero actions after
                                # it has already been paid for (for example a
                                # Call to Glory with no friendly units).
                                if target_min and not candidates:
                                    continue
                                if target_min and spec.get("target_pairs") is not None and not target_pairs:
                                    continue
                                result.append(Action.make(
                                    "play_spell_targeted", card=card,
                                    target_candidates=candidates,
                                    target_min=target_min,
                                    target_max=target_max,
                                    allow_repeat=bool(spec.get("allow_repeat", False)),
                                    target_pairs=target_pairs or None,
                                    ordered_pairs=code in {"OGN-108", "OGN-128", "OGN-260"},
                                    target_might_limit=4 if code in CONSTRAINED_MULTI_TARGET_SPELLS else None,
                                    same_location=code in CONSTRAINED_MULTI_TARGET_SPELLS,
                                    destination=None if code in DESTINATION_TARGET_SPELLS else destination,
                                    destination_select=code in DESTINATION_TARGET_SPELLS,
                                    spend_buff=spend,
                                    payment=payment,
                                    deck_options=list(row["main"][:3]) if code == "OGN-183" else None))
                                targeted_added = True
        return result

    def _registry_spell_target_candidates(self, state, player, scope):
        """Resolve target ids for a registered expansion spell.

        The registry stores the target shape, while this shared resolver owns
        zone/ownership rules.  This keeps an expansion card from inventing a
        one-off target path in ``apply`` and gives the GUI the same candidate
        list as policies and replays.
        """
        if scope == "any_unit":
            return [unit["id"] for unit in state["units"]
                    if self._is_targetable(state, player, unit["id"])]
        if scope in {"friendly_unit", "friendly_field_unit"}:
            return [unit["id"] for unit in self._units(state, player)
                    if scope == "friendly_unit" or self._is_field(state, unit["location"])]
        if scope == "any_gear":
            return [gear["id"] for row in state["players"]
                    for gear in row.get("gear", [])]
        if scope == "field_unit":
            return [unit["id"] for unit in state["units"]
                    if self._is_field(state, unit["location"])
                    and self._is_targetable(state, player, unit["id"])]
        if scope == "attacking_unit":
            battle = state.get("battle")
            if battle is None:
                return []
            return [unit["id"] for unit in self._units(
                state, battle["attacker"], battle["field"])]
        if scope == "field_unit_might_le_2":
            return [unit["id"] for unit in state["units"]
                    if self._is_field(state, unit["location"])
                    and self.might(state, unit) <= 2
                    and self._is_targetable(state, player, unit["id"])]
        raise ValueError(f"unknown registered spell target scope: {scope}")

    def _chain_item_chooses_friendly_target(self, state, item, counter_player):
        """Whether an opposing Chain item currently chooses its controller's unit/Gear."""
        if item.get("owner") == counter_player:
            return False
        target_ids = list(item.get("targets") or [])
        if item.get("target") is not None:
            target_ids.append(item["target"])
        if not target_ids:
            return False
        owner = item.get("owner")
        for target_id in target_ids:
            unit = self._unit(state, target_id)
            if unit is not None and unit.get("owner") == owner:
                return True
            gear = next((gear for row in state["players"] for gear in row.get("gear", [])
                         if gear.get("id") == target_id), None)
            if gear is not None and gear.get("owner") == owner:
                return True
        return False

    def _unit_actions(self, state):
        player = state["actor"]
        row = state["players"][player]
        result = []
        if self._cards_locked(state, player):
            return result
        locations = [f"base:{player}"] + [i for i, f in enumerate(state["fields"]) if f["controller"] == player]
        if self._warden_active(state, player):
            locations = [f"base:{player}"]
        for card in row["hand"] + row["champion"]:
            code = state["cards"][card]["code"]
            if not (code in UNIT_CODES or self._is_executable_kind(code, "unit")):
                continue
            if state["phase"] in {"chain", "showdown"} and not self._is_reaction_code(code):
                continue
            data = self.cards[code]
            implementation = self._card_implementation(code)
            permitted = locations.copy()
            if implementation and implementation.placement_rule == "attacking_battlefield":
                battle = state.get("battle")
                if (state["phase"] in {"chain", "showdown"} and battle is not None
                        and battle.get("attacker") == player
                        and self._is_field(state, battle.get("field"))):
                    permitted = [battle["field"]]
                else:
                    permitted = []
            if implementation and implementation.placement_rule == "occupied_enemy_field":
                permitted += [i for i in range(len(state["fields"]))
                              if any(unit["owner"] != player and unit["location"] == i
                                     for unit in state["units"])
                              and i not in permitted]
            if implementation and implementation.placement_rule == "conquered_field_this_turn":
                permitted = [i for i in state.get("scored", [[], []])[player]
                             if i not in permitted]
            if code in {"OGN-174", "OGN-176", "OGN-193"}:
                permitted += [i for i in range(len(state["fields"])) if not self._units(state, location=i) and i not in permitted]
            if any(other["owner"] == player and other["code"] == "OGN-193"
                   for other in state["units"]):
                permitted += [i for i in range(len(state["fields"]))
                              if not self._units(state, location=i) and i not in permitted]
            if code == "OGN-161":
                permitted += [i for i in range(len(state["fields"]))
                              if any(u["owner"] != player and u["location"] == i for u in state["units"])
                              and i not in permitted]
            energy = data["energy"] - (2 if code == "OGN-012" and self._played_for_legion(state, player) else 0)
            if implementation and implementation.cost_reduction_effect == "cards_played_floor_one":
                energy = max(1, energy - self._played_for_legion(state, player))
            if implementation and implementation.cost_reduction_effect == "hold_points":
                energy = max(0, energy - 2 * state.get("hold_points", [0, 0])[player])
            if "Dragon" in data["tags"] and any(u["code"] == "OGN-140" and u["owner"] == player
                                                  and self._is_field(u["location"]) for u in state["units"]):
                energy = max(1, energy - 2)
            if code == "OGN-195":
                energy = max(1, energy - len(row["trash"]))
            additional_energy = (implementation.additional_cost_energy
                                 if implementation is not None else
                                 (1 if code == "OGN-044" else 0))
            additional_power = (implementation.additional_cost_power
                                if implementation is not None else 0)
            sacrifices = ([unit["id"] for unit in self._units(state, player)]
                          if code == "OGN-208" else [None])
            extra_costs = ([False, True] if (additional_energy or additional_power)
                           and row["energy"] >= energy + additional_energy
                           else [False])
            discard_cards = ([None] + [uid for uid in row["hand"] if uid != card]
                             if code == "OGN-002" else [None])
            buff_slots = [unit["id"] for unit in self._units(state, player)
                          for _ in range(unit["buff"])] if code == "OGN-150" else []
            buff_spends = ([list(combo) for count in range(len(buff_slots) + 1)
                            for combo in combinations(buff_slots, count)]
                           if code == "OGN-150" else [[]])
            kill_options = ([list(combo) for count in range(len(self._units(state, player)) + 1)
                            for combo in combinations([unit["id"] for unit in self._units(state, player)], count)]
                           if code == "OGN-231" else [[]])
            additional_gear = ([gear["id"] for gear in row.get("gear", [])]
                               if implementation and implementation.additional_cost_effect == "return_gear"
                               else [None])
            if implementation and implementation.additional_cost_effect == "return_gear" and not additional_gear:
                continue
            # Accelerate is offered in a post-play payment window.  The
            # initial action therefore always pays only the printed unit cost;
            # the pending decision may later add one energy and one matching
            # domain power before the unit-entry continuation is finalized.
            for accelerate in [False]:
                for additional_cost in extra_costs:
                    for sacrifice in sacrifices:
                        for discard_card in discard_cards:
                            for spend_buffs in buff_spends:
                                for kill_units in kill_options:
                                    for returned_gear in additional_gear:
                                        total_energy = max(0, energy - (2 if discard_card else 0))
                                        total_energy += additional_energy if additional_cost else 0
                                        total_power = max(0, data["power_cost"] - len(spend_buffs) - len(kill_units))
                                        total_power += additional_power if additional_cost else 0
                                        for payment in self._payments(state, player, total_energy, data["domains"], total_power):
                                            for location in permitted:
                                                enter_targets = [None]
                                                if code == "OGN-016" and self._played_for_legion(state, player):
                                                    candidates = [unit["id"] for unit in self._units(state, player)]
                                                    enter_targets = candidates or [None]
                                                for enter_target in enter_targets:
                                                    result.append(Action.make(
                                                        "play_unit", card=card, location=location,
                                                        accelerate=accelerate, payment=payment,
                                                        enter_target=enter_target,
                                                        additional_cost=additional_cost,
                                                        sacrifice=sacrifice,
                                                        additional_discard=bool(discard_card),
                                                        discard_card=discard_card,
                                                        additional_gear=returned_gear,
                                                        spend_buffs=spend_buffs,
                                                        kill_units=kill_units))
                                                if code == "OGN-016" and self._played_for_legion(state, player) and candidates:
                                                    result.append(Action.make(
                                                        "play_unit_targeted", card=card, location=location,
                                                        accelerate=accelerate, payment=payment,
                                                        additional_cost=additional_cost, sacrifice=sacrifice,
                                                        target_candidates=candidates))
        return result

    def _movable(self, state, destination):
        player = state["actor"]
        base = f"base:{player}"
        if destination == base and any(
                (self._card_implementation(unit["code"]) is not None)
                and self._card_implementation(unit["code"]).global_effect == "no_base_moves"
                for unit in state["units"]):
            return []
        return [u["id"] for u in self._units(state, player) if not u["exhausted"]
                and u["location"] != destination
                and not (destination == base and self._is_field(state, u["location"])
                         and state["fields"][u["location"]]["code"] == "OGN-295")
                and ((destination == base and self._is_field(state, u["location"]))
                     or (self._is_field(state, destination) and (u["location"] == base or self._ganking(state, u))))]

    def _resolve_move(self, state, units, destination, initiator, rng, *, ready=False,
                      from_effect=False):
        """Resolve normal and effect moves through one rules path."""
        moved = [self._unit(state, uid) if isinstance(uid, str) else uid for uid in units]
        moved = [unit for unit in moved if unit is not None]
        if not moved:
            return False
        if (destination == f"base:{initiator}"
                and any(
                    (self._card_implementation(unit["code"]) is not None)
                    and self._card_implementation(unit["code"]).global_effect == "no_base_moves"
                    for unit in state["units"])):
            raise ValueError("units cannot move to base while Minotaur Reckoner is in play")
        origins = {unit["id"]: unit["location"] for unit in moved}
        move_triggers = []
        for unit in moved:
            if unit["owner"] != initiator and not from_effect:
                raise ValueError("cannot move an enemy unit with a normal move")
            origin = origins[unit["id"]]
            if (destination == f"base:{unit['owner']}" and self._is_field(state, origin)
                    and state["fields"][origin]["code"] == "OGN-295"):
                raise ValueError("Vilemaw's Lair prevents moving to base")
            unit["location"] = destination
            if ready:
                self._ready_unit(state, unit)
            else:
                unit["exhausted"] = True
            unit["move_count"] = unit.get("move_count", 0) + 1
            if unit["code"] == "OGN-205" and unit["move_count"] == 3:
                state["points"][unit["owner"]] += 1
            if self._is_field(state, destination):
                for watcher in self._units(state, location=None):
                    if (watcher["code"] == "OGN-158" and watcher["owner"] != initiator
                            and state["fields"][destination]["controller"] != watcher["owner"]):
                        self._draw(state, watcher["owner"], 1, rng if rng is not None else random.Random(0))
            if (self._is_field(state, origin)
                    and state["fields"][origin]["code"] == "OGN-277"):
                unit["temporary"] += 1
            implementation = self._card_implementation(unit["code"])
            if implementation and implementation.move_effect == "draw_one":
                self._draw(state, unit["owner"], 1,
                           rng if rng is not None else random.Random(0))
            if implementation and implementation.move_effect == "play_gold_gear":
                self._play_gold_gear_token(state, unit["owner"], exhausted=True)
            if (implementation and implementation.move_effect == "buff_self_two_from_field"
                    and self._is_field(state, origin)):
                unit["temporary"] += 2
            if (implementation and implementation.move_effect == "buff_another_on_move"
                    and self._is_field(state, destination)):
                move_triggers.append({"effect": "buff_another_on_move",
                                       "source": unit["id"], "owner": unit["owner"],
                                       "location": destination})
            if (implementation and implementation.move_effect == "discard_one"
                    and self._is_field(state, destination)):
                move_triggers.append({"effect": "discard_one",
                                       "source": unit["id"], "owner": unit["owner"]})
            if (implementation and implementation.move_effect == "apprentice_smith"
                    and self._is_field(state, destination)):
                move_triggers.append({"effect": "apprentice_smith",
                                       "source": unit["id"], "owner": unit["owner"]})
            if (implementation and implementation.move_effect == "score_on_third_move"
                    and unit["move_count"] == 3):
                state["points"][unit["owner"]] += 1
            if (implementation and implementation.move_effect == "play_recruit_three"
                    and self._is_field(state, destination)):
                for _ in range(3):
                    self._new_unit(state, TOKEN, unit["owner"], destination)
        # Stealthy Pursuer follows a friendly move from its location only
        # through an explicit optional window.  The printed ability says
        # "may"; accepting the window exhausts the Pursuer and moves it to
        # the same destination.  Queue it after the ordinary move has
        # established its showdown context so declining/accepting cannot
        # bypass the normal movement result.
        moved_ids = {unit["id"] for unit in moved}
        friendly_origins = {origins[unit["id"]] for unit in moved if unit["owner"] == initiator}
        pursuer_followers = []
        for watcher in list(self._units(state, initiator)):
            if (watcher["code"] == "OGN-177" and watcher["id"] not in moved_ids
                    and not watcher["exhausted"] and watcher["location"] in friendly_origins):
                pursuer_followers.append(watcher)
        self._cleanup(state, rng)
        entered_showdown = False
        if self._is_field(state, destination):
            enemies = self._units(state, 1 - initiator, destination)
            if state["fields"][destination]["controller"] != initiator or enemies:
                entered_showdown = True
                state["battle"] = {"field": destination, "attacker": initiator,
                                    "combat": bool(enemies)}
                state["focus"], state["passes"] = initiator, 0
                if from_effect:
                    # A spell/ability resolving on the chain resumes into
                    # showdown; an ability activated directly during Main
                    # moves there now.
                    if state["phase"] == "chain":
                        state["pending_showdown"] = True
                    else:
                        state["phase"], state["actor"] = "showdown", initiator
                else:
                    state["phase"], state["actor"] = "showdown", initiator
        for watcher in pursuer_followers:
            self._queue_optional(state, initiator, "stealthy_pursuer_follow",
                                 source=watcher["id"], destination=destination)
        for unit in moved:
            if unit["code"] == "OGN-162" and unit.get("move_count", 0) == 1:
                if any(other["owner"] == initiator and other["id"] != unit["id"]
                       and other["exhausted"] for other in state["units"]):
                    self._queue_optional(state, initiator, "miss_fortune_ready",
                                         source=unit["id"])
        if move_triggers:
            self._triggers(state, move_triggers, preserve_context=from_effect)
        return entered_showdown

    def legal_actions(self, state):
        if state["winner"] is not None:
            return ()
        phase, player = state["phase"], state["actor"]
        if phase == "optional":
            optional = state.get("optional", [])
            if not optional or optional[0]["player"] != player:
                return ()
            if (len(optional) > 1 and not state.get("optional_ordered", False)
                    and all(item["player"] == player for item in optional)):
                return tuple(Action.make("order_optional", order=[item["id"] for item in ordering])
                             for ordering in permutations(optional))
            item = optional[0]
            return (Action.make("optional_effect", optional=item["id"], accept=True),
                    Action.make("optional_effect", optional=item["id"], accept=False))
        if phase == "reveal":
            reveal = state.get("reveal")
            if not reveal:
                return ()
            if reveal["kind"] == "display":
                return (Action.make("end_reveal"),) if player == reveal["closer"] else ()
            if reveal["kind"] == "reorder":
                if player != reveal["chooser"]:
                    return ()
                cards = list(reveal.get("cards", []))
                return tuple(Action.make("order_revealed", order=list(order))
                             for order in permutations(cards))
            if player != reveal["chooser"]:
                return ()
            selected = list(reveal.get("selected", []))
            actions = [Action.make("choose_revealed", card=uid)
                       for uid in reveal.get("choices", reveal["cards"])
                       if uid not in selected and len(selected) < reveal["max"]]
            if len(selected) >= reveal["min"]:
                actions.append(Action.make("confirm_revealed"))
            return tuple(actions)
        if phase == "decision":
            decision = state["decision"]
            if decision["kind"] == "divine":
                if player != decision["player"]:
                    return ()
                actions = []
                for zone, values in decision.get("choices", {}).items():
                    selected = decision.get("selected", {}).get(zone, [])
                    if len(selected) < decision.get("required", {}).get(zone, 0):
                        actions.extend(Action.make("choose_divine", zone=zone, card=value)
                                       for value in values if value not in selected)
                    elif len(selected) < 2:
                        actions.extend(Action.make("choose_divine", zone=zone, card=value)
                                       for value in values if value not in selected)
                if all(len(decision.get("selected", {}).get(zone, [])) >= need
                       for zone, need in decision.get("required", {}).items()):
                    actions.append(Action.make("confirm_divine"))
                return tuple(actions)
            if decision["kind"] == "choice":
                actions = [Action.make("choose_option", option=option,
                                       **({"shakedown": True} if decision.get("shakedown") else {}))
                           for option in decision.get("options", [])]
                if decision.get("nocturne"):
                    if not self._payments(state, player, 0, DOMAINS, 0, 1):
                        actions = [a for a in actions
                                   if json.loads(a.arguments).get("option") != "nocturne_banish"]
                if decision.get("nocturne_play"):
                    if not self._payments(state, player, 0, DOMAINS, 0, 1):
                        actions = [a for a in actions
                                   if json.loads(a.arguments).get("option") != "nocturne_play"]
                if decision.get("nocturne_aurora_play"):
                    if not self._payments(state, player, 0, DOMAINS, 0, 1):
                        actions = [a for a in actions
                                   if json.loads(a.arguments).get("option") != "nocturne_play"]
                if decision.get("nocturne_aurora"):
                    if not self._payments(state, player, 0, DOMAINS, 0, 1):
                        actions = [a for a in actions
                                   if json.loads(a.arguments).get("option") != "nocturne_banish"]
                # Accelerate is paid during the play transaction.  Basic rune
                # Add-resource reactions remain available in this narrow
                # window so the player can exhaust/recycle runes before
                # confirming the additional cost; no other main-phase action
                # is exposed while the unit entry is pending.
                if decision.get("accelerate"):
                    row = state["players"][player]
                    domains = set(decision["accelerate"].get("domains", []))
                    # Rune/gear/legend Add-resource actions are separate
                    # payment actions. Accelerate itself is offered only once
                    # the current pools can actually pay its [1] + [C].
                    can_energy = row["energy"] >= 1
                    if len(domains) == 1:
                        can_power = any(power in domains or power == "any" for power in row["power"])
                    else:
                        # Radiance patch: [C] becomes [A] when the accelerated
                        # unit has no or multiple domains, so any one power is
                        # a legal payment after resource activation.
                        can_power = bool(row["power"])
                    if not (can_energy and can_power):
                        actions = [action for action in actions
                                   if json.loads(action.arguments).get("option") != "accelerate"]
                    for rune in row["runes"]:
                        if not rune["exhausted"]:
                            actions.append(Action.make("exhaust_rune", rune=rune["id"]))
                        actions.append(Action.make("recycle_rune", rune=rune["id"]))
                    actions.extend(self._accelerate_resource_actions(state, player))
                return tuple(actions)
            if decision["kind"] == "free_play_payment":
                if player != decision.get("player"):
                    return ()
                return tuple(Action.make("choose_payment", payment=list(payment))
                             for payment in decision.get("payments", []))
            if decision["kind"] == "predict":
                return (Action.make("predict", recycle=False), Action.make("predict", recycle=True))
            if decision["kind"] == "field":
                return tuple(Action.make("choose_field", field=field)
                             for field in decision.get("fields", []))
            if decision["kind"] == "chain_target":
                return tuple(Action.make("choose_chain_target", target=target)
                             for target in decision.get("targets", []))
            if decision["kind"] == "target":
                if decision.get("multi"):
                    selected = list(decision.get("selected", []))
                    selected_set = set(selected)
                    actions = [Action.make("choose_target", target=uid)
                               for uid in decision["targets"]
                               if decision.get("allow_repeat") or uid not in selected_set]
                    complete = len(selected) >= decision.get("min", 1)
                    if decision.get("target_pairs"):
                        complete = self._target_pair_matches(decision, list(selected))
                    if complete:
                        actions.append(Action.make("confirm_targets"))
                    if decision.get("cancel_play"):
                        actions.append(Action.make("cancel_play", card=decision["cancel_play"]["card"]))
                    return tuple(actions)
                actions = [Action.make("choose_target", target=uid)
                           for uid in decision["targets"]]
                if decision.get("cancel_play"):
                    actions.append(Action.make("cancel_play", card=decision["cancel_play"]["card"]))
                return tuple(actions)
            if decision["kind"] == "unit_target":
                return tuple(Action.make("choose_target", target=uid)
                             for uid in decision["targets"])
            if decision["kind"] == "hand_card":
                return tuple(Action.make("choose_card", card=uid)
                             for uid in decision.get("cards", []))
            return tuple(Action.make("discard_card", card=uid) for uid in state["players"][player]["hand"])
        if phase == "mulligan":
            hand = state["players"][player]["hand"]
            return tuple(Action.make("mulligan", slots=list(slots)) for n in range(3)
                         for slots in combinations(range(len(hand)), n))
        if phase == "trigger_order":
            return tuple(Action.make("order_triggers", order=list(order))
                         for order in permutations(range(len(state["pending"]))))
        if phase == "move_select":
            selection = state["selection"]
            actions = [Action.make("cancel_move")]
            if selection["units"]:
                actions.append(Action.make("commit_move"))
            actions.extend(Action.make("select_unit", unit=uid)
                           for uid in self._movable(state, selection["destination"]) if uid not in selection["units"])
            return tuple(actions)
        if phase == "damage":
            damage = state["battle"]["damage"]
            targets = self._units(state, 1-player, state["battle"]["field"])
            unassigned = [u for u in targets if u["id"] not in damage["assignments"][player]]
            last_units = [u for u in unassigned if u["code"] == "OGN-068"]
            eligible = [u for u in unassigned if u["code"] != "OGN-068"] if last_units and len(unassigned) > len(last_units) else last_units or unassigned
            tanks = [u for u in eligible if self._tank(u)]
            choices = tanks or eligible or targets
            return tuple(Action.make("assign_damage", target=u["id"]) for u in choices)
        result = self._resource_actions(state) + self._gear_actions(state) + self._hidden_actions(state) + self._spell_actions(state)
        if phase in {"chain", "showdown"}:
            # Reaction units use the same payment and placement path as main-
            # phase units; `_unit_actions` filters out non-Reaction units and
            # therefore safely exposes only legal response plays here.
            result.extend(self._unit_actions(state))
            result.append(Action.make("pass"))
        elif phase == "main":
            result.extend(self._unit_actions(state))
            for destination in (f"base:{player}", *range(len(state["fields"]))):
                if self._movable(state, destination):
                    result.append(Action.make("begin_move", destination=destination))
            result.append(Action.make("end_turn"))
        else:
            raise ValueError(f"unknown phase {phase}")
        return tuple(result)

    def _enter_chain(self, state, items, *, preserve_context=False):
        for item in items:
            # Preserve the player who completed the play process separately
            # from ``owner``.  Counter/reversal effects may later change the
            # resolving item's controller, but Legion and post-play triggers
            # still belong to the player who actually played the card.
            if item.get("card") is not None:
                item.setdefault("played_by", item.get("owner"))
        if not state["chain"] and not preserve_context:
            state["chain_return"] = state["phase"]
            state["chain_from_spell"] = any(item["effect"] == "spell" for item in items)
        state["chain"].extend(items)
        state["phase"], state["actor"], state["passes"] = "chain", items[-1]["owner"], 0
        self._arm_chain_top(state)

    def _triggers(self, state, triggers, *, preserve_context=False):
        """Put simultaneous triggered abilities on the Chain in rule order.

        RUP5 383.3.d--e requires one controller to order their own
        simultaneous triggers, then proceeds from the Turn Player in Turn
        Order when multiple players control triggers.  The old implementation
        exposed one permutation window for all owners, allowing the first
        owner to put the opponent's triggers on the Chain.  Grouping by owner
        keeps each choice private and appends the groups in APNAP/turn order;
        the last group added remains the first to resolve from the Chain.
        """
        triggers = list(triggers or [])
        if not triggers:
            return
        if len(triggers) == 1:
            self._enter_chain(state, triggers, preserve_context=preserve_context)
            return
        turn_player = state.get("turn_player", 0)
        owner_order = [turn_player, 1 - turn_player]
        groups = []
        for owner in owner_order:
            group = [item for item in triggers if item.get("owner", owner) == owner]
            if group:
                groups.append(group)
        # Preserve malformed/future-source trigger records without silently
        # dropping them; unknown owners are assigned after the two players and
        # remain orderable by the turn player.
        known = {id(item) for group in groups for item in group}
        remainder = [item for item in triggers if id(item) not in known]
        if remainder:
            groups.append(remainder)
        if len(groups) == 1 and len(groups[0]) == 1:
            self._enter_chain(state, groups[0], preserve_context=preserve_context)
            return
        state["pending_trigger_groups"] = groups[1:]
        state["pending"] = groups[0]
        state["ordered_triggers"] = []
        state["order_return"] = state["phase"]
        state["preserve_chain_context"] = preserve_context
        state["phase"], state["actor"] = "trigger_order", groups[0][0].get("owner", turn_player)
        state["passes"] = 0

    def _trigger_target_candidates(self, state, item):
        """Return targets for a triggered ability during its finalization.

        RUP5 403.2 requires choices for triggered abilities before priority is
        passed. The older implementation opened these windows only when the
        effect resolved, which let both players respond before the controller
        had finalized the trigger. Keep the candidate rules beside the effect
        handlers so resolution remains a defensive fallback.
        """
        owner = item.get("owner")
        effect = item.get("effect")
        source = item.get("source")
        if owner not in (0, 1):
            return None
        if effect == "kill_target":
            return [u["id"] for u in state["units"] if u["owner"] != owner]
        if effect == "stun_target":
            return [u["id"] for u in state["units"]]
        if effect == "buff_eight":
            return [u["id"] for u in self._units(state, owner)]
        if effect == "ready_target":
            return [u["id"] for u in self._units(state, owner) if u["id"] != source]
        if effect == "buff_target":
            return [u["id"] for u in self._units(state, owner) if u["id"] != source]
        if effect == "buff_another_on_move":
            location = item.get("location")
            return [u["id"] for u in self._units(state, owner, location)
                    if u["id"] != source]
        if effect == "return_unit_trigger":
            return [uid for uid in state["players"][owner]["trash"]
                    if self.cards[state["cards"][uid]["code"]]["type"] == "unit"]
        if effect == "return_gear_from_trash":
            return [uid for uid in state["players"][owner]["trash"]
                    if self.cards[state["cards"][uid]["code"]]["type"] == "gear"]
        if effect == "ready_another_friendly_mech":
            return [unit["id"] for unit in self._units(state, owner)
                    if unit["id"] != source
                    and "Mech" in self.cards.get(unit["code"], {}).get("tags", [])]
        if effect == "solari_target":
            return [u["id"] for u in state["units"] if u["owner"] != owner]
        if effect == "buff_two":
            return [u["id"] for u in self._units(state, owner) if u["id"] != source]
        if effect == "ganking_target":
            return [u["id"] for u in state["units"]]
        if effect == "kill_small_enemy":
            return [u["id"] for u in state["units"]
                    if u["owner"] != owner and self.might(state, u) <= 3]
        if effect == "blast_corps":
            return [u["id"] for u in state["units"]
                    if self._is_field(state, u["location"])
                    and self._is_targetable(state, owner, u["id"])]
        if effect == "frostcoat_debuff":
            return [u["id"] for u in state["units"]
                    if self._is_targetable(state, owner, u["id"])]
        if effect == "kinkou_buff":
            return [u["id"] for u in self._units(state, owner) if u["id"] != source]
        if effect == "ahri_debuff":
            field = state.get("battle", {}).get("field")
            return [u["id"] for u in self._units(state, 1 - owner, field)] \
                if self._is_field(state, field) else []
        if effect == "karma_recycle":
            return [u["id"] for u in self._units(state, owner)]
        if effect == "blitz_move":
            source_unit = self._unit(state, source)
            field = source_unit["location"] if source_unit is not None else None
            return [u["id"] for u in self._units(state, 1 - owner, field)] if self._is_field(state, field) else []
        if effect in {"crackshot_target", "leona_stun_target"}:
            field = state.get("battle", {}).get("field")
            return [u["id"] for u in self._units(state, 1 - owner, field)] if self._is_field(state, field) else []
        if effect == "yasuo_attack_target":
            field = state.get("battle", {}).get("field")
            return [u["id"] for u in self._units(state, 1 - owner, field)] if self._is_field(state, field) else []
        if effect in {"volibear_attack", "teemo_defend"}:
            field = item.get("field") or state.get("battle", {}).get("field")
            return [u["id"] for u in self._units(state, 1 - owner, field)] if self._is_field(state, field) else []
        if effect == "riptide_damage":
            return [u["id"] for u in state["units"]
                    if u["owner"] != owner and self._is_field(state, u["location"])]
        if effect == "snapvine_fight":
            return [u["id"] for u in state["units"]
                    if u["owner"] != owner and self._is_field(state, u["location"])]
        if effect == "fae_debuff":
            field = item.get("hidden_field")
            return [u["id"] for u in state["units"]
                    if field is None or u["location"] == field]
        if effect == "return_field_unit":
            return [u["id"] for u in state["units"]
                    if u["id"] != source and self._is_field(state, u["location"])]
        if effect == "return_friendly_enemy":
            # Beast Below has one mandatory two-target trigger.  The trigger
            # record carries the legal friendly/enemy pairs so the shared
            # click-to-select window can reject a same-side or source target
            # before the ability enters the Chain.
            return [u["id"] for u in state["units"]
                    if u["id"] != source]
        if effect == "move_field_unit":
            return [u["id"] for u in state["units"] if self._is_field(state, u["location"])]
        if effect == "tideturner_target":
            original = item.get("original_location")
            return [u["id"] for u in self._units(state, owner)
                    if u["id"] != source and u["location"] != original]
        if effect == "spirit_refuge":
            return [u["id"] for u in self._units(state, owner)]
        if effect == "vanguard_helm":
            return [u["id"] for u in self._units(state, owner)]
        return None

    def _arm_chain_top(self, state):
        """Finalize target choices for the newest triggered chain item."""
        while state.get("chain"):
            item = state["chain"][-1]
            if item.get("trigger_target_finalized") or item.get("target") is not None:
                return False
            targets = self._trigger_target_candidates(state, item)
            if targets is None:
                return False
            targets = [uid for uid in targets if self._is_targetable(state, item["owner"], uid)]
            if not targets and (not item.get("target_multi") or item.get("target_min", 0) > 0):
                # RUP5 403.4: an already-triggered ability with no legal
                # choices is removed from the Chain and never resolves.
                state["chain"].pop()
                continue
            item["trigger_target_pending"] = True
            state["decision"] = {
                "kind": "target", "player": item["owner"],
                "targets": targets, "item": item,
                "trigger_target": True,
                "multi": bool(item.get("target_multi")),
                "min": item.get("target_min", 0 if item.get("target_multi") else 1),
                "max": item.get("target_max", 2 if item.get("target_multi") else 1),
                "allow_repeat": bool(item.get("target_allow_repeat")),
                "selected": [],
                "target_pairs": [list(pair) for pair in item.get("target_pairs", [])],
                "ordered_pairs": bool(item.get("ordered_pairs", False)),
            }
            state["phase"], state["actor"] = "decision", item["owner"]
            state["passes"] = 0
            return True
        return False

    def _new_unit(self, state, code, owner, location, *, card=None, exhausted=None):
        if exhausted is None:
            exhausted = not any(u["code"] == "OGN-011" for u in self._units(state, owner))
        if (exhausted and self.cards.get(code, {}).get("token")
                and self._tokens_enter_ready(state, owner)):
            exhausted = False
        card_owner = state.get("cards", {}).get(card, {}).get("owner", owner) if card is not None else owner
        implementation = self._card_implementation(code)
        assault = (3 if self._has_static_keyword(code, "assault_3")
                   else 2 if self._has_static_keyword(code, "assault_2")
                   else 1 if self._has_static_keyword(code, "assault_1") else 0)
        unit = {"id": self._object(state), "card": card, "card_owner": card_owner,
                "code": code, "owner": owner,
                "location": location, "exhausted": exhausted, "buff": 0,
                "temporary": 0, "temporary_unit": False, "temporary_ganking": False,
                "temporary_tank": False, "combat_shield": 0, "assault": assault,
                "udyr_choices": [],
                "damage": 0, "stunned": False, "move_count": 0,
                "kill_on_damage": None, "prevent_next_damage": 0}
        if implementation and implementation.static_keywords:
            unit["static_keywords"] = sorted(implementation.static_keywords)
        state["units"].append(unit)
        return unit

    def _tokens_enter_ready(self, state, player):
        return any(
            unit["owner"] == player
            and (self._card_implementation(unit["code"]) is not None)
            and self._card_implementation(unit["code"]).global_effect == "tokens_enter_ready"
            for unit in state["units"]
        )

    def _second_card_triggers(self, state, player):
        # The current card is still pending when this helper is called.  A
        # second-card trigger therefore means exactly one *previous* card has
        # finalized this turn; testing the old ``played == 2`` shape here
        # would be fragile during nested/reaction plays.
        if self._played_for_legion(state, player) != 1:
            return []
        return [{"effect": "darius", "source": u["id"], "owner": player}
                for u in self._units(state, player) if u["code"] == "OGN-027"]

    def _pay(self, row, energy, slots):
        row["energy"] -= energy
        row["power"] = [power for index, power in enumerate(row["power"]) if index not in slots]

    def _finish_unit_play(self, state, pending, rng):
        """Finish a unit play after any Accelerate payment decision.

        Accelerate is a replacement effect during play (RUP5 805.2/805.6),
        so the unit is represented on the board while its payment window is
        open, but no later play triggers or showdown are processed until that
        window closes.  Keeping this continuation in one helper ensures the
        normal unit-entry path is identical for accelerated and non-accelerated
        units.
        """
        player = pending["player"]
        location = pending["location"]
        triggers = pending.get("triggers", [])
        unit = self._unit(state, pending.get("unit"))
        if unit is None:
            return
        state["phase"], state["actor"], state["passes"] = "main", player, 0
        row = state["players"][player]
        if pending.get("scrapyard_discard") and row["hand"]:
            state["decision"] = {"kind": "discard", "player": player,
                                  "remaining": min(2, len(row["hand"])),
                                  "scrapyard_discard": True,
                                  "post_triggers": triggers,
                                  "finalized_card": unit.get("card")}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return
        if pending.get("scrapyard_discard"):
            self._draw(state, player, 2, rng)
        self._mark_play_finalized(state, player, unit.get("card"),
                                  trigger_sink=triggers, rng=rng)
        if pending.get("replay_optional"):
            self._queue_optional(state, player, "replay_trash_unit",
                                 source=pending["unit"], code=pending["code"])
            self._cleanup(state, rng)
            return
        self._cleanup(state, rng)
        if state["winner"] is not None:
            return
        if (self._is_field(state, location)
                and state["fields"][location]["controller"] != player):
            state["battle"] = {"field": location, "attacker": player, "combat": False}
            state["phase"], state["focus"], state["passes"] = "showdown", player, 0
        self._triggers(state, triggers)

    # Effect handlers return False only when they opened a decision window and
    # the chain must remain paused.  All other handlers return True after their
    # effect has resolved; the registry caller then advances the chain.
    def _effect_darius(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source:
            source["temporary"] += 2
            self._ready_unit(state, source)
        return True

    def _effect_buff_self(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        self._apply_buff(state, source)
        return True

    def _effect_ravenbloom(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is not None and source["code"] == "OGN-103":
            source["temporary"] += 1
        return True

    def _effect_ahri_debuff(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        field = state.get("battle", {}).get("field")
        if (target is not None and self._is_field(state, field)
                and target["location"] == field and target["owner"] != item["owner"]):
            target["temporary"] -= 2
        return True

    def _effect_crackshot_target(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        field = state.get("battle", {}).get("field")
        if (target is not None and self._is_field(state, field)
                and target["location"] == field and target["owner"] != item["owner"]):
            self._deal_damage(state, target, 1)
            self._cleanup(state, rng)
        return True

    def _effect_leona_stun_target(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        field = state.get("battle", {}).get("field")
        if (target is not None and self._is_field(state, field)
                and target["location"] == field and target["owner"] != item["owner"]):
            target["stunned"] = True
            self._radiant_stun_trigger(state, item["owner"])
        return True

    def _effect_yasuo_attack_target(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        target = self._unit(state, item.get("target"))
        field = state.get("battle", {}).get("field")
        if (source is not None and target is not None and self._is_field(state, field)
                and source["location"] == field and target["location"] == field
                and target["owner"] != item["owner"]):
            self._deal_damage(state, target, self.might(state, source))
            self._cleanup(state, rng)
        return True

    def _effect_riptide_damage(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if (target is not None and target["owner"] != item["owner"]
                and self._is_field(state, target["location"])):
            self._deal_damage(state, target, 6)
            self._cleanup(state, rng)
        return True

    def _effect_fae_debuff(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is not None:
            target["temporary"] -= 2
        return True

    def _effect_return_field_unit(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is None or not self._is_field(state, target["location"]):
            return True
        state["units"].remove(target)
        card = target.get("card")
        if card is not None:
            self._hand_unit_card(state, target)
        return True

    def _effect_return_friendly_enemy(self, state, item, rng):
        """Resolve Beast Below's paired return as one atomic effect.

        Target legality is fixed when the triggered ability is finalized.  At
        resolution each selected unit is still checked against its controller
        and the source exclusion, then both physical cards are returned to
        their owners' hands through the shared zone-transfer helper.
        """
        targets = list(item.get("targets") or [])
        if len(targets) != 2:
            return True
        source = self._unit(state, item.get("source"))
        units = [self._unit(state, target_id) for target_id in targets]
        if any(unit is None for unit in units) or len({unit["id"] for unit in units}) != 2:
            return True
        friendly = next((unit for unit in units
                         if unit["owner"] == item.get("owner")
                         and (source is None or unit["id"] != source["id"])), None)
        enemy = next((unit for unit in units
                      if unit["owner"] != item.get("owner")), None)
        if friendly is None or enemy is None:
            return True
        for unit in (friendly, enemy):
            if unit in state["units"]:
                state["units"].remove(unit)
                self._hand_unit_card(state, unit)
        return True

    def _effect_optional_return_small_field_unit(self, state, item, rng):
        """Queue Windsinger's optional small-unit return target."""
        candidates = [unit["id"] for unit in state["units"]
                      if self._is_field(state, unit["location"])
                      and self.might(state, unit) <= 3
                      and unit["id"] != item.get("source")]
        if not candidates:
            return True
        self._queue_optional(state, item["owner"], "return_small_field_unit",
                             source=item.get("source"), candidates=candidates)
        return True

    def _effect_loyal_pup_defend(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        field = item.get("field")
        if (source is None or source["owner"] != item["owner"]
                or source["location"] != f"base:{item['owner']}"
                or not self._is_field(state, field)):
            return True
        self._queue_optional(state, item["owner"], "loyal_pup_move",
                             source=source["id"], destination=field,
                             resume="close_showdown")
        return True

    def _effect_overzealous_fan_defend(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        field = item.get("field")
        if (source is None or source["owner"] != item["owner"]
                or source["location"] != field or not self._is_field(state, field)):
            return True
        if not any(unit["owner"] != item["owner"] and unit["location"] == field
                   for unit in state["units"]):
            return True
        self._queue_optional(state, item["owner"], "fan_return_attacker",
                             source=source["id"], field=field,
                             resume="close_showdown")
        return True

    def _effect_ready_friendly_units(self, state, item, rng):
        for unit in self._units(state, item["owner"]):
            self._ready_unit(state, unit)
        return True

    def _effect_draven_might(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        field = item.get("field")
        if (source is None or source["owner"] != item["owner"]
                or source["location"] != field or not self._is_field(state, field)):
            return True
        if not state["players"][item["owner"]]["power"]:
            return True
        self._queue_optional(state, item["owner"], "draven_might",
                             source=source["id"], field=field,
                             resume="close_showdown")
        return True

    def _players_hand(self, state, player):
        return state["players"][player]["hand"]

    @staticmethod
    def _card_owner(state, card, fallback):
        """Return the physical owner of a card, independent of control."""
        return state.get("cards", {}).get(card, {}).get("owner", fallback)

    def _unit_card_owner(self, state, unit):
        card = unit.get("card")
        return unit.get("card_owner", self._card_owner(state, card, unit["owner"]))

    def _gear_card_owner(self, state, gear):
        card = gear.get("card")
        return gear.get("card_owner", self._card_owner(state, card, gear["owner"]))

    def _trash_card(self, state, card, fallback):
        if card is not None:
            code = state.get("cards", {}).get(card, {}).get("code")
            if code is not None and self.cards.get(code, {}).get("token"):
                return
            state["players"][self._card_owner(state, card, fallback)]["trash"].append(card)

    def _play_gold_gear_token(self, state, player, *, exhausted=True):
        """Create the SFD Gold gear token as a non-physical card object."""
        if exhausted and self._tokens_enter_ready(state, player):
            exhausted = False
        token = self._object(state)
        state["cards"][token] = {"code": "SFD-T03", "owner": player}
        state["players"][player]["gear"].append({
            "id": token, "card": token, "code": "SFD-T03",
            "owner": player, "card_owner": player,
            "location": f"base:{player}", "exhausted": exhausted,
            "temporary": False,
        })
        return token

    def _trash_unit_card(self, state, unit):
        self._trash_card(state, unit.get("card"), self._unit_card_owner(state, unit))

    def _hand_unit_card(self, state, unit):
        card = unit.get("card")
        if card is not None:
            code = state.get("cards", {}).get(card, {}).get("code")
            if code is not None and self.cards.get(code, {}).get("token"):
                return
            row = state["players"][self._unit_card_owner(state, unit)]
            if card not in row["hand"]:
                row["hand"].append(card)

    def _trash_gear_card(self, state, gear):
        self._trash_card(state, gear.get("card"), self._gear_card_owner(state, gear))

    def _hand_gear_card(self, state, gear):
        card = gear.get("card")
        if card is not None:
            code = state.get("cards", {}).get(card, {}).get("code")
            if code is not None and self.cards.get(code, {}).get("token"):
                return
            row = state["players"][self._gear_card_owner(state, gear)]
            if card not in row["hand"]:
                row["hand"].append(card)

    def _effect_move_field_unit(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is not None and self._is_field(state, target["location"]):
            self._resolve_move(state, [target], f"base:{target['owner']}", item["owner"], rng,
                               from_effect=True)
        return True

    def _effect_poro_herder(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is not None and any("Poro" in self.cards[u["code"]]["tags"]
                                      for u in self._units(state, item["owner"])):
            self._apply_buff(state, source)
            self._draw(state, item["owner"], 1, rng)
        return True

    def _effect_sprite_mother(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is not None:
            token = self._new_unit(state, SPRITE_TOKEN, item["owner"], source["location"], exhausted=False)
            token["temporary_unit"] = True
        return True

    def _effect_watcher_debuff(self, state, item, rng):
        for unit in self._units(state, 1 - item["owner"]):
            unit["temporary"] -= 3
        return True

    def _effect_buff_self_three(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is not None:
            source["temporary"] += 3
        return True

    def _effect_viktor_innovator(self, state, item, rng):
        token = self._new_unit(state, TOKEN, item["owner"], f"base:{item['owner']}", exhausted=False)
        return True

    def _effect_kadregrin_draw(self, state, item, rng):
        mighty = sum(self.might(state, unit) >= 5
                     for unit in self._units(state, item["owner"]))
        if mighty:
            self._draw(state, item["owner"], mighty, rng)
        return True

    def _effect_portal_rescue(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is None or target["owner"] != item["owner"]:
            return True
        owner = target["owner"]
        card = target.get("card")
        code = target["code"]
        if target in state["units"]:
            state["units"].remove(target)
        if card is not None:
            state["players"][owner]["banishment"].append(card)
            state["players"][owner]["banishment"].remove(card)
        self._new_unit(state, code, owner, f"base:{owner}", card=card, exhausted=True)
        return True

    def _effect_snapvine_fight(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        target = self._unit(state, item.get("target"))
        if source is not None and target is not None and target["owner"] != item["owner"]:
            self._deal_damage(state, source, self.might(state, target))
            self._deal_damage(state, target, self.might(state, source))
            self._cleanup(state, rng)
        return True

    def _consume_gear(self, state, item):
        gear = next((g for g in state["players"][item["owner"]]["gear"]
                     if g["id"] == item.get("gear")), None)
        if gear is None or gear["exhausted"]:
            return None
        gear["exhausted"] = True
        self._gear_ability_used(state, item["owner"])
        return gear

    def _gear_ability_used(self, state, player):
        """Apply the shared post-activation listener for gear abilities."""
        for unit in self._units(state, player):
            implementation = self._card_implementation(unit["code"])
            if implementation and implementation.global_effect == "prize_progress":
                unit["temporary"] += 1

    def _effect_gear_damage(self, state, item, rng):
        if self._consume_gear(state, item) is None:
            return True
        target = self._unit(state, item.get("target"))
        if target is not None and self._is_field(state, target["location"]):
            self._deal_damage(state, target, 2)
            self._cleanup(state, rng)
        return True

    def _effect_gear_buff_three(self, state, item, rng):
        """Heart of Dark Ice: exhaust to give any unit +3 this turn."""
        if self._consume_gear(state, item) is None:
            return True
        target = self._unit(state, item.get("target"))
        if target is not None:
            target["temporary"] += 3
        return True

    def _effect_gear_draw(self, state, item, rng):
        """Poro Snax's activated ability consumes the Gear, then draws one."""
        gear = next((g for g in state["players"][item["owner"]]["gear"]
                     if g["id"] == item.get("gear")), None)
        if gear is None or gear.get("exhausted"):
            return True
        state["players"][item["owner"]]["gear"].remove(gear)
        self._trash_gear_card(state, gear)
        self._gear_ability_used(state, item["owner"])
        self._draw(state, item["owner"], 1, rng)
        return True

    def _effect_gear_return(self, state, item, rng):
        if self._consume_gear(state, item) is None:
            return True
        owner = item["owner"]
        row = state["players"][owner]
        target = self._unit(state, item.get("target"))
        if target is not None:
            if target["owner"] != owner:
                return True
            state["units"].remove(target)
            self._hand_unit_card(state, target)
            return True
        gear = next((g for g in row["gear"] if g["id"] == item.get("target")), None)
        if gear is not None and gear["id"] != item.get("gear"):
            row["gear"].remove(gear)
            self._hand_gear_card(state, gear)
            return True
        hidden = next((h for h in row.get("hidden", []) if h["id"] == item.get("target")), None)
        if hidden is not None:
            row["hidden"].remove(hidden)
            row["hand"].append(hidden["card"])
        return True

    def _effect_gear_debuff(self, state, item, rng):
        if self._consume_gear(state, item) is None:
            return True
        target = self._unit(state, item.get("target"))
        if target is not None:
            target["temporary"] -= 1
        return True

    def _effect_gear_buff_exhausted(self, state, item, rng):
        if self._consume_gear(state, item) is None:
            return True
        target = self._unit(state, item.get("target"))
        if target is not None and target["owner"] == item["owner"] and target["exhausted"]:
            self._apply_buff(state, target)
        return True

    def _effect_gear_move(self, state, item, rng):
        if self._consume_gear(state, item) is None:
            return True
        target = self._unit(state, item.get("target"))
        if target is not None and target["owner"] == item["owner"] and self._is_field(state, target["location"]):
            self._resolve_move(state, [target], f"base:{item['owner']}", item["owner"], rng, from_effect=True)
        return True

    def _effect_gear_armory_protect(self, state, item, rng):
        """Armory's one-turn death replacement.

        The printed cost includes discarding a card.  The target has already
        been chosen through the normal gear target window; consume the Gear,
        discard the first card in hand, and arm a replacement marker on the
        unit.  The marker is consumed by ``_cleanup`` if the unit would die.
        """
        gear = self._consume_gear(state, item)
        target = self._unit(state, item.get("target"))
        row = state["players"][item["owner"]]
        if gear is None or target is None or target["owner"] != item["owner"] or not row["hand"]:
            return True
        discarded = row["hand"].pop(0)
        row["trash"].append(discarded)
        row["discarded_this_turn"] = True
        target["death_replacement"] = {"kind": "armory", "turn": state["turn"]}
        return True

    def _effect_gear_baited_hook(self, state, item, rng):
        """Resolve Baited Hook's sacrifice and open its top-five window."""
        target = self._unit(state, item.get("target"))
        owner = item["owner"]
        row = state["players"][owner]
        gear = next((g for g in row["gear"] if g["id"] == item.get("gear")), None)
        copied_source = item.get("copied_source")
        if copied_source is not None:
            gear = self._unit(state, copied_source)
        if gear is None or (copied_source is None and gear["exhausted"]) \
                or target is None or target["owner"] != owner:
            return True
        if row["energy"] < 1:
            return True
        order_index = next((i for i, power in enumerate(row["power"]) if power == "order"), None)
        if order_index is None:
            return True
        # A native Gear action exhausts the Gear object.  A copied action has
        # already exhausted Heimer as its activating source.
        gear["exhausted"] = True
        row["energy"] -= 1
        row["power"].pop(order_index)
        killed_might = self.might(state, target)
        target["damage"] = self.might(state, target)
        self._cleanup(state, rng)
        top = list(row["main"][:5])
        if not top:
            return True
        choices = [uid for uid in top
                   if self.cards[state["cards"][uid]["code"]]["type"] == "unit"
                   and self.cards[state["cards"][uid]["code"]]["might"] <= killed_might + 1]
        self._open_reveal(state, owner=owner, cards=top, mode="select", chooser=owner,
                          minimum=0, maximum=1, effect="baited_hook", choices=choices, rng=rng)
        return True

    def _effect_spirit_refuge(self, state, item, rng):
        """Spirit's Refuge entry trigger: buff one friendly unit.

        Deflect is derived dynamically by ``_deflect`` while the Gear and the
        unit's buff remain in play, so the trigger only needs to apply the
        ordinary buff marker.
        """
        owner = item["owner"]
        if item.get("target") is None:
            return self._open_target_choice(
                state, item, self._units(state, owner))
        target = self._unit(state, item["target"])
        if target is not None and target["owner"] == owner:
            self._apply_buff(state, target)
        return True

    def _effect_vanguard_helm(self, state, item, rng):
        """Vanguard Helm buffs one other friendly unit after a buffed death."""
        owner = item["owner"]
        target = self._unit(state, item.get("target"))
        if target is not None and target["owner"] == owner:
            self._apply_buff(state, target)
        return True

    def _effect_mindsplitter(self, state, item, rng):
        """Mindsplitter reveals the opponent's hand, then chooses one card."""
        owner = item["owner"]
        opponent = 1 - owner
        if item.get("reveal_done"):
            return True
        hand = list(state["players"][opponent]["hand"])
        if not hand:
            return True
        # The opponent's hand is public for the duration of the selection,
        # but the caster must explicitly choose and confirm the discarded
        # card.  Reuse the generic reveal/select window so this remains
        # compatible with future hand-selection effects.
        self._open_reveal(state, owner=opponent, cards=hand, mode="select",
                          chooser=owner, minimum=1, maximum=1,
                          closer=owner, effect="mindsplitter", item=item,
                          choices=hand, rng=rng)
        return False

    def _effect_baited_hook_finish(self, state, item, rng):
        """Recycle Baited Hook's unselected cards after its free play resolves."""
        owner = item["owner"]
        remaining = [uid for uid in item.get("remaining", [])
                     if uid in state["players"][owner]["main"]]
        self._recycle_cards_to_main(state, owner, remaining, source="main", rng=rng)
        return True

    def _begin_dazzling_aurora(self, state, player, rng):
        """Open one public top-card reveal for Aurora.

        Aurora uses the same reveal window as every other look effect. The
        continuation item stays on the Chain while recycled cards, Karma, and
        the eventual free play resolve, so nested triggers cannot overwrite an
        end-turn-specific side path.
        """
        row = state["players"][player]
        current = state.get("aurora_current_gear")
        if current is not None and any(gear["id"] == current for gear in row["gear"]):
            if row["main"]:
                top = row["main"][0]
                self._open_reveal(
                    state, owner=player, cards=[top], mode="display",
                    chooser=1 - player, closer=1 - player,
                    effect="dazzling_aurora", item={
                        "effect": "dazzling_aurora_continue", "owner": player,
                        "aurora_gear": current,
                    }, choices=[top], rng=rng)
                return False
            state.pop("aurora_current_gear", None)
        while state.get("aurora_queue"):
            gear_id = state["aurora_queue"].pop(0)
            if any(gear["id"] == gear_id for gear in row["gear"]):
                state["aurora_current_gear"] = gear_id
                if row["main"]:
                    top = row["main"][0]
                    self._open_reveal(
                        state, owner=player, cards=[top], mode="display",
                        chooser=1 - player, closer=1 - player,
                        effect="dazzling_aurora", item={
                            "effect": "dazzling_aurora_continue", "owner": player,
                            "aurora_gear": gear_id,
                        }, choices=[top], rng=rng)
                    return False
                break
        state.pop("aurora_current_gear", None)
        state.pop("aurora_queue", None)
        state.pop("end_turn_pending", None)
        self._finish_end_turn(state, player, rng)
        return True

    def _effect_dazzling_aurora_continue(self, state, item, rng):
        """Resume Aurora after the preceding reveal/free play has settled."""
        if item.get("advance_gear"):
            state.pop("aurora_current_gear", None)
        return self._begin_dazzling_aurora(state, item["owner"], rng)

    def _effect_peak(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source:
            self._apply_buff(state, source)
            if self._is_field(state, source["location"]):
                for unit in self._units(state, item["owner"], source["location"]):
                    self._apply_buff(state, unit)
        return True

    def _effect_drummer(self, state, item, rng):
        self._new_unit(state, TOKEN, item["owner"], item["location"])
        return True

    def _effect_vision(self, state, item, rng):
        owner = item["owner"]
        row = state["players"][owner]
        if row["main"]:
            top = row["main"][0]
            # Nocturne's replacement window is private to the player looking
            # at the top card.  It must resolve before Vision's ordinary
            # recycle choice, so the opponent never learns the card identity.
            if state["cards"][top]["code"] == "OGN-194":
                state["decision"] = {
                    "kind": "choice", "player": owner,
                    "options": ["nocturne_banish", "nocturne_skip"],
                    "nocturne": {"card": top, "item": item, "owner": owner},
                }
                state["phase"], state["actor"] = "decision", owner
                return False
            state["decision"] = {"kind": "predict", "player": owner, "remaining": 1}
            state["phase"], state["actor"] = "decision", owner
            return False
        return True

    def _effect_discard_two(self, state, item, rng):
        owner = item["owner"]
        hand = state["players"][owner]["hand"]
        state["players"][owner]["discarded_this_turn"] = True
        if hand:
            state["decision"] = {"kind": "discard", "player": owner,
                                  "remaining": min(2, len(hand))}
            state["phase"], state["actor"] = "decision", owner
            return False
        return True

    def _effect_discard_one(self, state, item, rng):
        owner = item["owner"]
        hand = state["players"][owner]["hand"]
        state["players"][owner]["discarded_this_turn"] = True
        if hand:
            state["decision"] = {"kind": "discard", "player": owner, "remaining": 1}
            state["phase"], state["actor"] = "decision", owner
            return False
        return True

    def _effect_apprentice_smith(self, state, item, rng):
        """Apprentice Smith's move trigger uses the shared public reveal window."""
        owner = item["owner"]
        top = list(state["players"][owner]["main"][:1])
        if not top:
            return True
        self._open_reveal(state, owner=owner, cards=top, mode="display",
                          chooser=1 - owner, closer=1 - owner,
                          effect="apprentice_smith", item=item,
                          choices=top, rng=rng)
        return False

    def _effect_yordle_explorer(self, state, item, rng):
        """Resolve one Yordle Explorer draw after its play event."""
        source = self._unit(state, item.get("source"))
        if source is not None and source["owner"] == item["owner"]:
            self._draw(state, item["owner"], 1, rng)
        return True

    def _open_target_choice(self, state, item, targets, *, multi=False, minimum=1, maximum=None,
                            allow_repeat=False):
        """Pause a chain item until its controller chooses legal target(s).

        Single-target effects keep the original one-click behaviour.  Multi-target
        effects expose a persistent selection window: each ``choose_target`` adds
        one id and the controller must explicitly submit ``confirm_targets``.
        This keeps target choice visible to the UI and prevents the engine from
        silently taking the first legal combination.
        """
        target_ids = [u["id"] if isinstance(u, dict) else u for u in targets]
        if not target_ids and minimum:
            return True
        maximum = len(target_ids) if maximum is None else (
            maximum if allow_repeat else min(maximum, len(target_ids)))
        if multi and maximum < minimum:
            return True
        decision = {"kind": "target", "player": item["owner"],
                    "targets": target_ids, "item": item}
        if multi:
            decision.update({"multi": True, "min": minimum, "max": maximum, "selected": [],
                             "allow_repeat": allow_repeat})
        state["decision"] = decision
        state["phase"], state["actor"] = "decision", item["owner"]
        return False

    def _complete_free_play_unit_target(self, state, info, target, rng,
                                        payment_override=None):
        """Finish a free unit play after its entry target is confirmed.

        Target selection is a part of the play process.  Keep the physical
        card in its source zone until both the target and any required
        payment are confirmed; this is especially important for nested free
        plays because an aborted child must leave its parent continuation
        intact.
        """
        owner, card = info["owner"], info["card"]
        data = self.cards[state["cards"][card]["code"]]
        payment = payment_override
        if payment is None:
            if info.get("free_all"):
                payment = []
            else:
                required_energy = (0 if info.get("ignore_energy") else
                                   max(0, data["energy"] - int(info.get("energy_reduction", 0))))
                choices = self._payments(state, owner, required_energy,
                                         data["domains"], data["power_cost"])
                if not choices:
                    self._abandon_free_play(state, info)
                    return
                if len(choices) > 1:
                    state["decision"] = {
                        "kind": "free_play_payment", "player": owner,
                        "payments": choices, "targets": [target],
                        "free_play_unit": {
                            **info, "payment": None, "enter_target": target,
                        },
                    }
                    state["phase"], state["actor"], state["passes"] = (
                        "decision", owner, 0)
                    return
                payment = choices[0]
        physical = state["players"][info.get("card_owner", owner)]
        row = state["players"][owner]
        if card in physical.get("banishment", []):
            physical["banishment"].remove(card)
        if card not in row["hand"]:
            row["hand"].append(card)
        state["decision"] = None
        state["phase"], state["actor"], state["passes"] = "chain", owner, 0
        self.apply(state, Action.make(
            "play_unit", card=card, location=f"base:{owner}",
            accelerate=False, payment=list(payment or []),
            enter_target=target,
            ignore_cost=((not info.get("ignore_energy")
                          and not info.get("energy_reduction"))
                         or bool(info.get("free_all"))),
            ignore_energy=bool(info.get("ignore_energy")) or bool(info.get("free_all")),
            energy_reduction=int(info.get("energy_reduction", 0)),
            free_play_parent=True), rng)
        parent = info.get("parent")
        if (parent is not None and parent in state.get("chain", [])
                and state.get("phase") == "main"):
            state["phase"], state["actor"] = "chain", state["chain"][-1]["owner"]

    def _complete_free_play_target(self, state, decision, selected, rng):
        """Move a revealed card into the controller's hand and play it.

        The replacement card is kept in its physical owner's zone until this
        point, so a pending target choice never creates an illegal cross-owner
        hand entry.  ``play_spell`` then uses the ordinary chain and post-spell
        trigger machinery with Energy ignored but Power already paid.
        """
        info = decision["free_play"]
        owner, card = info["owner"], info["card"]
        if (info.get("ignore_energy") and not info.get("free_all")
                and info.get("payment") is None):
            deflect = sum(
                self._deflect(state, target)
                for uid in selected
                for target in [self._unit(state, uid)]
                if target is not None and target["owner"] != owner)
            data = self.cards[state["cards"][card]["code"]]
            payment_options = [(None, self._payments(
                state, owner, 0, data["domains"], data["power_cost"],
                deflect, spell=True))]
            if data["code"] in {"OGN-146", "OGN-207"}:
                payment_options.extend(
                    (uid, self._payments(state, owner, 0, data["domains"], 0,
                                         deflect, spell=True))
                    for uid in [u["id"] for u in self._units(state, owner) if u["buff"]])
            payment_options = [(spend, choices) for spend, choices in payment_options if choices]
            if not payment_options:
                self._abandon_free_play(state, info)
                return
            if len(payment_options) > 1:
                payment_map = {
                    ("power" if spend is None else f"buff:{spend}"): choices
                    for spend, choices in payment_options
                }
                state["decision"] = {
                    "kind": "choice", "player": owner,
                    "options": list(payment_map),
                    "free_play_buff": {
                        **info, "selected": list(selected),
                        "payment_options": payment_map,
                    },
                }
                state["phase"], state["actor"], state["passes"] = "decision", owner, 0
                return
            spend_buff, choices = payment_options[0]
            if len(choices) > 1:
                state["decision"] = {
                    "kind": "free_play_payment", "player": owner,
                    "payments": choices, "targets": list(selected),
                    "free_play_spell": {
                        **info, "payment": None, "spend_buff": spend_buff,
                        "selected": list(selected),
                    },
                }
                state["phase"], state["actor"], state["passes"] = "decision", owner, 0
                return
            info["payment"], info["spend_buff"] = choices[0], spend_buff
        physical = state["players"][info.get("card_owner", owner)]
        row = state["players"][owner]
        if card in physical.get("banishment", []):
            physical["banishment"].remove(card)
        if card not in row["hand"]:
            row["hand"].append(card)
        state["decision"] = None
        # Kai'Sa's replay is started from an optional/main-phase continuation;
        # other reveal replacements are already resolving inside their parent
        # Chain item.  Preserve that return phase so an empty nested Chain does
        # not leave the engine stuck in ``phase=chain``.
        parent = info.get("parent") or {}
        resume_phase = "main" if parent.get("effect") == "kaisa_replay_spell" else "chain"
        state["phase"], state["actor"], state["passes"] = resume_phase, owner, 0
        self.apply(state, Action.make(
            "play_spell", card=card, targets=list(selected),
            destination=info.get("destination"), spend_buff=info.get("spend_buff"),
            payment=list(info.get("payment", [])),
            ignore_cost=(not bool(info.get("ignore_energy")) or bool(info.get("free_all"))),
            ignore_energy=bool(info.get("ignore_energy")) or bool(info.get("free_all")),
            deck_options=list(info.get("deck_options", [])),
            free_play_parent=True), rng)
        if parent.get("effect") == "kaisa_replay_spell":
            for entry in reversed(state.get("chain", [])):
                if entry.get("card") == card:
                    entry["recycle_after"] = True
                    break

    def _complete_free_play_field(self, state, info, rng):
        """Finish a free replay whose spell chooses a battlefield (and X)."""
        owner, card = info["owner"], info["card"]
        field = info.get("field")
        if field not in info.get("fields", []):
            raise ValueError("free-play battlefield is unavailable")
        if (info.get("ignore_energy") and not info.get("free_all")
                and info.get("payment") is None):
            data = self.cards[state["cards"][card]["code"]]
            choices = self._payments(
                state, owner, 0, data["domains"], data["power_cost"], spell=True)
            if not choices:
                self._abandon_free_play(state, info)
                return
            if len(choices) > 1:
                state["decision"] = {
                    "kind": "free_play_payment", "player": owner,
                    "payments": choices, "targets": [],
                    "free_play_field": {**info, "payment": None},
                }
                state["phase"], state["actor"], state["passes"] = "decision", owner, 0
                return
            info["payment"] = choices[0]
        x = int(info.get("x", 0))
        row = state["players"][owner]
        if x < 0 or x > len(row.get("power", [])):
            raise ValueError("invalid free-play X payment")
        if x:
            self._pay(row, 0, list(range(x)))
        physical = state["players"][info.get("card_owner", owner)]
        if card in physical.get("banishment", []):
            physical["banishment"].remove(card)
        if card not in row["hand"]:
            row["hand"].append(card)
        state["decision"] = None
        parent = info.get("parent") or {}
        resume_phase = "main" if parent.get("effect") == "kaisa_replay_spell" else "chain"
        state["phase"], state["actor"], state["passes"] = resume_phase, owner, 0
        self.apply(state, Action.make(
            "play_spell", card=card, targets=[], destination=None,
            field=field, x=x, spend_buff=None,
            payment=list(info.get("payment") or []),
            ignore_cost=(not bool(info.get("ignore_energy")) or bool(info.get("free_all"))),
            ignore_energy=bool(info.get("ignore_energy")) or bool(info.get("free_all")),
            free_play_parent=True), rng)
        if parent.get("effect") == "kaisa_replay_spell":
            for entry in reversed(state.get("chain", [])):
                if entry.get("card") == card:
                    entry["recycle_after"] = True
                    break

    @staticmethod
    def _abandon_free_play(state, info):
        """Close an unpayable free-play window without inventing a payment.

        The replacement card remains in its current physical zone.  The
        parent Chain (or Kai'Sa's Main-phase continuation) resumes normally,
        so an unavailable Power/Deflect payment cannot strand the game in a
        decision with no legal actions.
        """
        parent = info.get("parent") or {}
        state["decision"] = None
        state["phase"] = ("main" if parent.get("effect") == "kaisa_replay_spell"
                           or not state.get("chain") else "chain")
        state["actor"] = info.get("owner", state.get("turn_player", 0))
        state["passes"] = 0

    def _effect_kill_target(self, state, item, rng):
        if item.get("target") is None:
            return self._open_target_choice(state, item,
                                            [u for u in state["units"] if u["owner"] != item["owner"]])
        target = self._unit(state, item["target"])
        if target is not None and target["owner"] != item["owner"]:
            target["damage"] = self.might(state, target)
            self._cleanup(state, rng)
        return True

    def _effect_stun_target(self, state, item, rng):
        if item.get("target") is None:
            return self._open_target_choice(state, item, list(state["units"]))
        target = self._unit(state, item.get("target"))
        if target is not None:
            target["stunned"] = True
            self._radiant_stun_trigger(state, item["owner"])
            self._stun_triggers(state, item["owner"])
        return True

    def _effect_buff_eight(self, state, item, rng):
        if item.get("target") is None:
            return self._open_target_choice(state, item,
                                            [u for u in state["units"] if u["owner"] == item["owner"]])
        target = self._unit(state, item.get("target"))
        if target is not None:
            target["temporary"] += 8
        return True

    def _effect_ready_target(self, state, item, rng):
        """Ready another friendly unit, opening a private target choice."""
        source = item.get("source")
        if item.get("target") is None:
            targets = [u for u in self._units(state, item["owner"])
                       if u["id"] != source]
            return self._open_target_choice(state, item, targets)
        target = self._unit(state, item["target"])
        if target is not None and target["owner"] == item["owner"] and target["id"] != source:
            self._ready_unit(state, target)
        return True

    def _effect_buff_target(self, state, item, rng):
        """Give another friendly unit its ordinary +1 buff."""
        source = item.get("source")
        if item.get("target") is None:
            targets = [u for u in self._units(state, item["owner"])
                       if u["id"] != source]
            return self._open_target_choice(state, item, targets)
        target = self._unit(state, item["target"])
        if target is not None and target["owner"] == item["owner"] and target["id"] != source:
            self._apply_buff(state, target)
        return True

    def _effect_return_unit_trigger(self, state, item, rng):
        owner = item["owner"]
        if item.get("target") is None:
            targets = [uid for uid in state["players"][owner]["trash"]
                       if self.cards[state["cards"][uid]["code"]]["type"] == "unit"]
            return self._open_target_choice(state, item, targets)
        trash = state["players"][owner]["trash"]
        if item["target"] in trash:
            trash.remove(item["target"])
            state["players"][owner]["hand"].append(item["target"])
        return True

    def _effect_return_gear_from_trash(self, state, item, rng):
        owner = item["owner"]
        trash = state["players"][owner]["trash"]
        target = item.get("target")
        if target is not None and target in trash:
            if self.cards[state["cards"][target]["code"]]["type"] == "gear":
                trash.remove(target)
                state["players"][owner]["hand"].append(target)
        return True

    def _effect_ready_another_friendly_mech(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if (target is not None and target["owner"] == item["owner"]
                and "Mech" in self.cards.get(target["code"], {}).get("tags", [])):
            self._ready_unit(state, target)
        return True

    def _effect_ganking_target(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is not None:
            target["temporary_ganking"] = True
        return True

    def _effect_kill_small_enemy(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is not None and target["owner"] != item["owner"] and self.might(state, target) <= 3:
            state["units"].remove(target)
            self._trash_unit_card(state, target)
            self._cleanup(state, rng)
        return True

    def _effect_blast_corps(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is not None and self._is_field(state, target["location"]):
            self._deal_damage(state, target, 2)
            self._cleanup(state, rng)
        return True

    def _effect_frostcoat_debuff(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is not None:
            target["temporary"] -= 2
        return True

    def _effect_lucian_attack(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        target = self._unit(state, item.get("target"))
        field = item.get("field") or state.get("battle", {}).get("field")
        if (source is not None and target is not None
                and target["owner"] != item["owner"]
                and source["location"] == field and target["location"] == field):
            self._deal_damage(state, target, source.get("assault", 0))
            self._cleanup(state, rng)
        return True

    def _effect_play_four_gold_gear(self, state, item, rng):
        for _ in range(4):
            self._play_gold_gear_token(state, item["owner"], exhausted=True)
        return True

    def _effect_optional_kill_gear(self, state, item, rng):
        """Queue Disarming Rake's optional gear destruction."""
        if any(row.get("gear") for row in state["players"]):
            self._queue_optional(state, item["owner"], "kill_gear",
                                 source=item.get("source"))
        return True

    def _effect_optional_kill_cheap_gear(self, state, item, rng):
        """Queue Pickpocket's optional destruction of a low-cost gear."""
        if any(self.cards.get(gear["code"], {}).get("energy", 99) <= 1
               for row in state["players"] for gear in row.get("gear", [])):
            self._queue_optional(state, item["owner"], "kill_cheap_gear",
                                 source=item.get("source"))
        return True

    def _effect_buff_another_on_move(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        source = self._unit(state, item.get("source"))
        if (target is not None and source is not None
                and target["owner"] == item["owner"]
                and target["id"] != source["id"]
                and target["location"] == item.get("location")):
            self._apply_buff(state, target)
        return True

    def _effect_legend_toggle(self, state, item, rng):
        row = state["players"][item["owner"]]
        if row.get("legend") is None:
            return True
        state["decision"] = {
            "kind": "choice", "player": item["owner"],
            "options": ["ready", "exhaust"],
            "item": item, "legend_toggle": True,
        }
        state["phase"], state["actor"], state["passes"] = "decision", item["owner"], 0
        return False

    def _effect_optional_draw_or_buff(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is not None and source["owner"] == item["owner"]:
            self._queue_optional(state, item["owner"], "draw_or_buff",
                                 source=source["id"])
        return True

    def _effect_discard_one_draw_two(self, state, item, rng):
        hand = state["players"][item["owner"]]["hand"]
        if not hand:
            self._draw(state, item["owner"], 2, rng)
            return True
        state["decision"] = {
            "kind": "discard", "player": item["owner"], "remaining": 1,
            "item": item, "discard_one_draw_two": True,
        }
        state["phase"], state["actor"], state["passes"] = "decision", item["owner"], 0
        return False

    def _effect_play_sand_soldier(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is not None:
            self._new_unit(state, "SFD-T04", item["owner"], source["location"])
        return True

    def _effect_kill_small_unit_and_gold(self, state, item, rng):
        target = self._unit(state, (item.get("targets") or [None])[0])
        if target is None or not self._is_field(state, target["location"]):
            return True
        if self.might(state, target) > 2:
            return True
        target_owner = target["owner"]
        state["units"].remove(target)
        self._trash_unit_card(state, target)
        for _ in range(2 if target_owner == item["owner"] else 1):
            self._play_gold_gear_token(state, item["owner"], exhausted=True)
        return True

    def _effect_buff_other_units_two(self, state, item, rng):
        source = item.get("source")
        for unit in self._units(state, item["owner"]):
            if unit["id"] != source:
                unit["temporary"] += 2
        return True

    def _effect_tideturner_target(self, state, item, rng):
        """Resolve Tideturner's atomic location swap.

        The source's original location is captured when its play trigger is
        created.  Both units then move simultaneously, so neither half of the
        swap can create an intermediate showdown or expose the other unit to a
        second movement effect.  Moving by a card effect still exhausts both
        units under the normal movement rules.
        """
        source = self._unit(state, item.get("source"))
        target = self._unit(state, item.get("target"))
        if source is None or target is None or source["owner"] != item["owner"] \
                or target["owner"] != item["owner"]:
            return True
        original = item.get("original_location", source["location"])
        if target["location"] == original:
            return True
        destination = target["location"]
        source["location"], target["location"] = destination, original
        source["exhausted"], target["exhausted"] = True, True
        source["move_count"] = source.get("move_count", 0) + 1
        target["move_count"] = target.get("move_count", 0) + 1
        # A swap can put either unit into an enemy-occupied battlefield.  Keep
        # the normal chain-to-showdown handoff without resolving a partial move.
        for moved in (source, target):
            location = moved["location"]
            if not self._is_field(state, location):
                continue
            enemies = self._units(state, 1 - item["owner"], location)
            if enemies:
                state["battle"] = {"field": location, "attacker": item["owner"],
                                    "combat": True}
                state["focus"], state["passes"] = item["owner"], 0
                if state.get("phase") == "chain":
                    state["pending_showdown"] = True
                else:
                    state["phase"], state["actor"] = "showdown", item["owner"]
                break
        return True

    def _effect_ember_hidden_buff(self, state, item, rng):
        """Ember Monk's Hidden play trigger grants +2 Might this turn."""
        source = self._unit(state, item.get("source"))
        if source is not None and source["code"] == "OGN-167":
            source["temporary"] += 2
        return True

    def _effect_karthus_deathknell(self, state, item, rng):
        """Marker handler kept explicit for future Deathknell extensions."""
        return True

    def _effect_solari_target(self, state, item, rng):
        if item.get("target") is None:
            return self._open_target_choice(
                state, item, [u for u in state["units"] if u["owner"] != item["owner"]])
        target = self._unit(state, item["target"])
        if target is None or target["owner"] == item["owner"]:
            return True
        if target["stunned"]:
            target["damage"] = self.might(state, target)
            self._cleanup(state, rng)
        else:
            target["stunned"] = True
            self._stun_triggers(state, item["owner"])
        return True

    def _effect_ready_self(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is not None:
            self._ready_unit(state, source)
        return True

    def _effect_twisted_fate(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if item.get("target") is not None and item.get("domain") in {"fury", "order"}:
            target = self._unit(state, item["target"])
            if target is not None:
                if item["domain"] == "fury":
                    self._deal_damage(state, target, 2)
                    for enemy in self._units(state, 1 - item["owner"], item.get("field")):
                        if enemy["id"] != target["id"]:
                            self._deal_damage(state, enemy, 1)
                else:
                    target["stunned"] = True
            return True
        if source is None or not state["players"][item["owner"]]["rune_deck"]:
            return True
        row = state["players"][item["owner"]]
        rune = row["rune_deck"].pop(0)
        row["rune_deck"].append({**rune, "exhausted": False})
        domain = self.cards[rune["code"]]["domains"][0]
        field = source["location"]
        enemies = [unit["id"] for unit in self._units(state, 1 - item["owner"], field)]
        if domain == "mind" or not enemies:
            if domain == "mind":
                self._draw(state, item["owner"], 1, rng)
            return True
        item["domain"], item["field"] = domain, field
        state["chain"].append(item)
        state["decision"] = {"kind": "target", "player": item["owner"],
                              "targets": enemies,
                              "item": item,
                              "twisted_fate": True}
        state["phase"], state["actor"], state["passes"] = "decision", item["owner"], 0
        return False

    def _effect_buff_two(self, state, item, rng):
        source = item.get("source")
        if item.get("target") is None:
            return self._open_target_choice(
                state, item, [u for u in self._units(state, item["owner"]) if u["id"] != source])
        target = self._unit(state, item["target"])
        if target is not None and target["owner"] == item["owner"]:
            target["temporary"] += 2
        return True

    def _effect_volibear_attack(self, state, item, rng):
        """Volibear, Furious: assign five damage points among enemy units here.

        The target window records one click per damage point.  Repeated clicks
        on the same unit are legal, which models the printed "split among any
        number" allocation while retaining an auditable order in the chain.
        """
        source = self._unit(state, item.get("source"))
        field = item.get("field")
        if source is None or not self._is_field(state, field):
            return True
        if item.get("targets") is None:
            targets = [u["id"] for u in self._units(state, 1 - item["owner"], field)]
            if not targets:
                return True
            return self._open_target_choice(state, item, [self._unit(state, uid) for uid in targets],
                                            multi=True, minimum=5, maximum=5, allow_repeat=True)
        targets = [self._unit(state, uid) for uid in item.get("targets", [])]
        targets = [target for target in targets
                   if target is not None and target["owner"] != item["owner"]
                   and target["location"] == field]
        if targets:
            # Each click assigns one of the five damage points.  Repeated
            # clicks are legal, so the player can put all five on one unit or
            # split them across any number of units in the chosen order.
            for target in targets:
                self._deal_damage(state, target, 1)
        self._cleanup(state, rng)
        return True

    def _effect_teemo_defend(self, state, item, rng):
        """Teemo, Strategist: reveal five cards and damage the chosen enemy.

        The reveal is public and the opponent closes the display window.  The
        top five cards remain in the Main Deck until the window closes, then
        all five are recycled and the number of Hidden cards determines the
        damage dealt.
        """
        target = self._unit(state, item.get("target"))
        if target is None or target["owner"] == item["owner"]:
            return True
        if not item.get("reveal_done"):
            top = list(state["players"][item["owner"]]["main"][:5])
            if not top:
                return True
            self._open_reveal(state, owner=item["owner"], cards=top, mode="display",
                              effect="teemo_defend", item=item, closer=1-item["owner"], rng=rng)
            return False
        hidden_count = int(item.get("hidden_count", 0))
        if hidden_count:
            self._deal_damage(state, target, hidden_count)
            self._cleanup(state, rng)
        return True

    def _effect_ava_attack(self, state, item, rng):
        """Ava Achiever's optional Hidden play opportunity."""
        source = self._unit(state, item.get("source"))
        if source is None or source["location"] != item.get("field"):
            return True
        candidates = [uid for uid in state["players"][item["owner"]]["hand"]
                      if self._is_hidden_code(state["cards"][uid]["code"])]
        if not candidates:
            return True
        self._queue_optional(state, item["owner"], "ava_play_hidden",
                             source=source["id"], candidates=candidates,
                             field=item.get("field"))
        return True

    def _effect_kinkou_buff(self, state, item, rng):
        for uid in item.get("targets", []):
            target = self._unit(state, uid)
            if target is not None and target["owner"] == item["owner"] and not target["buff"]:
                self._apply_buff(state, target)
        return True

    def _effect_albus_optional(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is None:
            return True
        if not any(unit["buff"] for unit in self._units(state, item["owner"])):
            return True
        self._queue_optional(state, item["owner"], "albus_channel", source=source["id"])
        return True

    def _effect_albus_channel(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is None or source["owner"] != item["owner"]:
            return True
        for uid in item.get("targets", []):
            target = self._unit(state, uid)
            if target is not None and target["owner"] == item["owner"] and target["buff"]:
                target["buff"] -= 1
                self._channel_rune(state, item["owner"], exhausted=True)
        return True

    def _effect_wildclaw_optional(self, state, item, rng):
        """Queue Wildclaw Shaman's optional buff-spend ability.

        The optional confirmation is deliberately separate from target choice:
        accepting the trigger opens a target window for a friendly unit that
        currently has a Buff, then consumes exactly one Buff from that unit.
        """
        source = self._unit(state, item.get("source"))
        if source is None:
            return True
        if not any(unit["id"] != source["id"] and unit["buff"]
                   for unit in self._units(state, item["owner"])):
            return True
        self._queue_optional(state, item["owner"], "wildclaw_ready", source=source["id"])
        return True

    def _effect_wildclaw_ready(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        target = self._unit(state, item.get("target"))
        if source is None or target is None or source["owner"] != item["owner"] \
                or target["owner"] != item["owner"] or not target["buff"]:
            return True
        target["buff"] -= 1
        self._apply_buff(state, source)
        self._ready_unit(state, source)
        return True

    def _effect_jinx_discard(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is not None and source["owner"] == item["owner"]:
            self._ready_unit(state, source)
            source["temporary"] += 1
        return True

    def _effect_karma_recycle(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is not None and target["owner"] == item["owner"]:
            self._apply_buff(state, target)
        return True

    def _effect_sabotage(self, state, item, rng):
        if item.get("reveal_done"):
            return True
        owner = item["owner"]
        opponent = 1 - owner
        cards = [uid for uid in state["players"][opponent]["hand"]
                 if self.cards[state["cards"][uid]["code"]]["type"] != "unit"]
        if not cards:
            # Sabotage still reveals the complete hand when no card is a legal
            # choice; the Sabotage caster closes the public display.
            self._open_reveal(state, owner=opponent,
                              cards=list(state["players"][opponent]["hand"]),
                              mode="display", chooser=owner, closer=owner,
                              effect=None, item=item)
            return False
        self._open_reveal(state, owner=opponent, cards=list(state["players"][opponent]["hand"]),
                          mode="select", chooser=owner, minimum=1, maximum=1,
                          effect="sabotage_recycle", item=item, choices=cards)
        return False

    def _effect_draw_one(self, state, item, rng):
        self._draw(state, item["owner"], 1, rng)
        return True

    def _effect_channel_one(self, state, item, rng):
        self._channel_rune(state, item["owner"], exhausted=True)
        return True

    def _effect_reaver_recall_target(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is not None and self._is_field(state, target["location"]):
            self._resolve_move(state, [target], f"base:{target['owner']}", item["owner"], rng,
                               from_effect=True)
        return True

    def _effect_blitz_move(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        target = self._unit(state, item.get("target"))
        if source is not None and target is not None and target["owner"] != item["owner"]:
            self._resolve_move(state, [target], source["location"], item["owner"], rng, from_effect=True)
        return True

    def _effect_adaptatron_conquer(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        gear = next((g for g in state["players"][item["owner"]]["gear"] if g["id"] == item.get("target")), None)
        if source is not None and gear is not None:
            state["players"][item["owner"]]["gear"].remove(gear)
            self._trash_gear_card(state, gear)
            self._apply_buff(state, source)
        return True

    def _effect_fortified_shield(self, state, item, rng):
        target = self._unit(state, item.get("target"))
        if target is not None and target["location"] == state.get("battle", {}).get("field"):
            target["combat_shield"] = 2
        return True

    def _effect_return_unit(self, state, item, rng):
        owner = item["owner"]
        if item.get("target") is None:
            targets = [uid for uid in state["players"][owner]["trash"]
                       if self.cards[state["cards"][uid]["code"]]["type"] == "unit"]
            if not targets:
                self._trash_card(state, item.get("card"), item.get("owner", owner))
                return True
            return self._open_target_choice(state, item, targets)
        trash = state["players"][owner]["trash"]
        if item["target"] in trash:
            trash.remove(item["target"])
            state["players"][owner]["hand"].append(item["target"])
        self._trash_card(state, item.get("card"), item.get("owner", owner))
        return True

    def _effect_harrowing_finish(self, state, item, rng):
        """Finish The Harrowing after its selected unit has been played.

        The original spell effect is already resolved before the trash-zone
        choice opens.  This continuation only performs the normal spell card
        cleanup and lets the shared Chain resolver generate its post-spell
        triggers; it never re-executes the selection effect.
        """
        self._trash_card(state, item.get("card"), item.get("owner"))
        return True

    def _effect_counter(self, state, item, rng):
        target_id = item.get("counter_target", "")
        try:
            index = int(str(target_id).split(":", 1)[1])
        except (ValueError, IndexError):
            if item.get("card") is not None:
                self._trash_card(state, item.get("card"), item["owner"])
            return True
        if index < 0 or index >= len(state.get("chain", [])):
            if item.get("card") is not None:
                self._trash_card(state, item.get("card"), item["owner"])
            return True
        target = state["chain"][index]
        code = item.get("code")
        valid_target = (self._chain_item_chooses_friendly_target(state, target, item["owner"])
                        if code == "SFD-045-221" else target.get("effect") == "spell")
        if target is item or not valid_target:
            if item.get("card") is not None:
                self._trash_card(state, item.get("card"), item["owner"])
            return True
        data = self.cards.get(target.get("code"), {})
        if code == "OGN-045" and (data.get("energy", 99) > 4 or data.get("power_cost", 99) > 1):
            self._trash_card(state, item.get("card"), item["owner"])
            return True
        if code == "OGN-080":
            target["owner"] = item["owner"]
            # Mystic Reversal takes control of the spell, then puts it back on
            # top of the Chain.  Its previous choices are cleared and the new
            # controller must make any legal target choices before priority
            # resumes.
            state["chain"].remove(target)
            target["targets"] = []
            # Any target/option selection made before the counter belongs to
            # the spell's prior controller.  Remove it before presenting the
            # new controller's window; retaining ``choice_done`` would let
            # choice spells resolve with a stale option without prompting.
            target.pop("choice", None)
            target.pop("choice_done", None)
            target.pop("destination", None)
            target.pop("field", None)
            target.pop("x", None)
            state["chain"].append(target)
            if item.get("card") is not None:
                self._trash_card(state, item.get("card"), item["owner"])
            spec = self._counter_retarget_spec(state, target)
            if spec is not None:
                if spec.get("kind") == "choice":
                    state["decision"] = {"kind": "choice",
                                          "player": spec.get("player", item["owner"]),
                                          "options": list(spec["options"]), "item": target,
                                          "counter_retarget_choice": True}
                elif spec.get("kind") == "field":
                    state["decision"] = {"kind": "field", "player": item["owner"],
                                          "fields": spec["fields"], "item": target,
                                          "counter_retarget": True,
                                          "x_choice": spec.get("x_choice", False),
                                          "x_max": spec.get("x_max", 0)}
                else:
                    state["decision"] = {"kind": "target", "player": item["owner"],
                                          "targets": spec["targets"], "item": target,
                                          "counter_retarget": True, **spec}
                if spec.get("kind") not in {"field", "choice"}:
                    state["decision"]["targets"] = spec["targets"]
                state["phase"], state["actor"], state["passes"] = (
                    "decision", state["decision"].get("player", item["owner"]), 0)
                return False
            return True
        state["chain"].remove(target)
        card = target.get("card")
        owner = target.get("owner")
        if card is not None and owner in (0, 1):
            self._trash_card(state, card, owner)
        self._trash_card(state, item.get("card"), item["owner"])
        return True

    def _counter_retarget_spec(self, state, item):
        """Return the immediate target window for a spell retaken by Mystic Reversal."""
        code = item.get("code")
        if code == "OGN-071":
            # Party Favors has a non-target choice.  Mystic Reversal's new
            # controller must make that choice again instead of inheriting the
            # original controller's selection.
            # Party Favors says "each other player"; after Mystic Reversal
            # changes control, the new controller's opponent still makes the
            # choice.  Keep this chooser explicit so future multiplayer
            # choice specs do not accidentally default to the spell owner.
            return {"kind": "choice", "options": ["cards", "runes"],
                    "player": 1 - item["owner"]}
        if code == "OGN-187":
            # Whirlwind starts with the next player, i.e. the opponent of the
            # current controller in the two-player simulator.
            options = ["skip"]
            if state.get("units"):
                options.insert(0, "return")
            return {"kind": "choice", "options": options,
                    "player": 1 - item["owner"]}
        if code == "OGN-237":
            return {"targets": [u["id"] for u in state["units"]
                                if u["owner"] != item["owner"]],
                    "multi": False, "min": 1, "max": 1}
        canonical = self._spell_target_spec(state, item["owner"], code)
        if canonical is not None:
            if canonical.get("kind") == "field":
                return {"kind": "field", "fields": list(canonical.get("fields", [])),
                        "x_choice": bool(canonical.get("x_choice")),
                        "x_max": len(state["players"][item["owner"]].get("power", []))}
            maximum = int(canonical.get("max", 1))
            minimum = int(canonical.get("min", 1))
            return {
                "targets": list(canonical.get("candidates", [])),
                "multi": bool(canonical.get("multi", maximum != 1 or minimum == 0
                                             or canonical.get("allow_repeat")
                                             or canonical.get("target_pairs"))),
                "min": minimum, "max": maximum,
                "allow_repeat": bool(canonical.get("allow_repeat", False)),
                "target_pairs": [list(pair) for pair in canonical.get("target_pairs", [])],
                "ordered_pairs": code in {"OGN-108", "OGN-128", "OGN-260"},
                "target_might_limit": canonical.get("target_might_limit"),
                "same_location": bool(canonical.get("same_location", False)),
                "destination_select": bool(canonical.get("destination_select", False)),
            }
        if code == "OGN-029":
            return {"targets": [u["id"] for u in state["units"]],
                    "multi": True, "min": 2, "max": 2, "allow_repeat": True}
        if code == "OGN-248":
            count = 2 if code == "OGN-029" else 6
            return {"targets": [u["id"] for u in state["units"] if self._is_field(state, u["location"])],
                    "multi": True, "min": count, "max": count, "allow_repeat": True}
        if code in PAIR_TARGET_SPELLS | {"OGN-105", "OGN-206"}:
            return {"targets": [u["id"] for u in state["units"]],
                    "multi": True, "min": 2, "max": 2,
                    "target_pairs": [[a["id"], b["id"]] for a in state["units"]
                                     for b in state["units"] if a["id"] != b["id"]]
                    if code in PAIR_TARGET_SPELLS else []}
        if code in DESTINATION_TARGET_SPELLS:
            candidates = [u["id"] for u in state["units"]]
            return {"targets": candidates, "multi": False, "min": 1, "max": 1,
                    "destination_select": True}
        if code == "OGN-266":
            return {"kind": "field", "fields": list(range(len(state["fields"]))) }
        if code == "OGN-268":
            return {"kind": "field", "fields": list(range(len(state["fields"]))),
                    "x_choice": True, "x_max": len(state["players"][item["owner"]]["power"])}
        if code == "OGN-256":
            candidates = [u["id"] for u in state["units"] if self._is_field(state, u["location"])]
            return {"targets": candidates, "multi": True, "min": 0, "max": len(candidates),
                    "target_might_limit": 4, "same_location": True}
        if code == "OGN-048":
            candidates = [u["id"] for u in self._units(state, item["owner"]) if not u["exhausted"]]
            return {"targets": candidates, "multi": True, "min": 0, "max": 1}
        if code in {"OGN-005", "OGN-008", "OGN-009", "OGN-014", "OGN-024", "OGN-085", "OGN-168", "OGN-172", "OGN-213"}:
            candidates = [u["id"] for u in state["units"] if self._is_field(state, u["location"])]
        elif code == "OGN-169":
            candidates = [u["id"] for u in state["units"]
                          if self._is_field(state, u["location"])
                          and self.might(state, u) <= 3]
        elif code == "OGN-180":
            candidates = ([u["id"] for u in state["units"] if self._is_field(state, u["location"])]
                          + [gear["id"] for row in state["players"] for gear in row["gear"]])
        elif code == "OGN-033":
            candidates = [u["id"] for u in self._units(state, 1 - item["owner"])]
        elif code in {"OGN-046", "OGN-069", "OGN-102", "OGN-146", "OGN-154", "OGN-207"}:
            candidates = [u["id"] for u in self._units(state, item["owner"])]
        else:
            candidates = [u["id"] for u in state["units"]]
        if code in SIMPLE_TARGET_SPELLS | {"OGN-008", "OGN-057"}:
            return {"targets": candidates, "multi": False, "min": 1, "max": 1}
        return None

    def _open_divine_choice(self, state, player):
        row = state["players"][player]
        choices = {"units": [u["id"] for u in self._units(state, player)],
                   "gear": [g["id"] for g in row["gear"]],
                   "runes": [r["id"] for r in row["runes"]],
                   "hand": list(row["hand"])}
        selected = state.setdefault("divine", {}).setdefault("selected", {}).setdefault(player, {})
        required = {zone: min(2, len(values)) for zone, values in choices.items()}
        state["decision"] = {"kind": "divine", "player": player,
                              "choices": choices, "selected": selected,
                              "required": required, "item": state["divine"]["item"]}
        state["phase"], state["actor"], state["passes"] = "decision", player, 0

    def _recycle_divine_rest(self, state, player, selected, rng):
        row = state["players"][player]
        selected = {zone: set(values) for zone, values in selected.items()}
        cards_by_owner = {0: [], 1: []}
        for unit in list(self._units(state, player)):
            if unit["id"] in selected.get("units", set()):
                continue
            state["units"].remove(unit)
            if unit.get("card") is not None:
                cards_by_owner[self._unit_card_owner(state, unit)].append(unit["card"])
        for gear in list(row["gear"]):
            if gear["id"] in selected.get("gear", set()):
                continue
            row["gear"].remove(gear)
            cards_by_owner[self._gear_card_owner(state, gear)].append(gear["card"])
        for rune in list(row["runes"]):
            if rune["id"] in selected.get("runes", set()):
                continue
            row["runes"].remove(rune)
            row["rune_deck"].append({**rune, "exhausted": False})
            players = state.setdefault("divine_recycle_players", [])
            if player not in players:
                players.append(player)
        for card in list(row["hand"]):
            if card not in selected.get("hand", set()):
                row["hand"].remove(card)
                cards_by_owner[player].append(card)
        for card_owner, cards in cards_by_owner.items():
            if not cards:
                continue
            # 417.5 randomizes only the cards recycled by this effect; keep
            # the existing Main Deck order intact and append a shuffled batch.
            rng.shuffle(cards)
            state["players"][card_owner]["main"].extend(cards)
            players = state.setdefault("divine_recycle_players", [])
            if card_owner not in players:
                players.append(card_owner)

    def _finish_divine_choice(self, state, player, rng):
        divine = state.get("divine")
        if divine is None:
            raise ValueError("Divine Judgment choice is unavailable")
        selected = divine.setdefault("selected", {}).setdefault(player, {})
        self._recycle_divine_rest(state, player, selected, rng)
        divine["index"] += 1
        if divine["index"] < len(divine["players"]):
            self._open_divine_choice(state, divine["players"][divine["index"]])
            return
        item = divine["item"]
        item["divine_done"] = True
        state.pop("divine", None)
        state["decision"] = None
        state["chain"].append(item)
        # Recycle triggers (Karma) are emitted only after both players finish
        # their selections, so a trigger cannot interrupt the second player's
        # Divine Judgment window.
        for recycle_player in state.pop("divine_recycle_players", []):
            self._trigger_recycle_event(state, recycle_player)
        state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
        self._finish_resolution(state)

    def _fox_fire_legal_subsets(self, state, item):
        """Return maximum-cardinality legal subsets of Fox-Fire's targets.

        RUP5 355.11.b/.b.1 treats Fox-Fire as a group target. Reactions can
        make the original group illegal, but resolution may only choose from
        those original targets and must keep the largest legal subset. A
        target that left the board is unavailable; targets that moved together
        to another battlefield remain eligible.
        """
        original = list(dict.fromkeys(item.get("fox_fire_initial_targets",
                                             item.get("targets", []))))
        groups = {}
        hidden_field = item.get("hidden_field")
        for uid in original:
            unit = self._unit(state, uid)
            if unit is None or not self._is_field(state, unit.get("location")):
                continue
            if hidden_field is not None and unit["location"] != hidden_field:
                continue
            groups.setdefault(unit["location"], []).append(unit)
        legal = []
        for units in groups.values():
            for count in range(1, len(units) + 1):
                for subset in combinations(units, count):
                    if sum(self.might(state, unit) for unit in subset) <= 4:
                        legal.append(tuple(unit["id"] for unit in subset))
        if not legal:
            return original, 0, []
        maximum = max(len(subset) for subset in legal)
        best = [subset for subset in legal if len(subset) == maximum]
        candidates = sorted({uid for subset in best for uid in subset}, key=str)
        return original, maximum, candidates

    def _effect_spell(self, state, item, rng):
        code, owner = item["code"], item["owner"]
        implementation = self._card_implementation(code)
        if implementation and implementation.spell_effect == "assault_two":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is not None:
                target["assault"] += 2
            return True
        if implementation and implementation.spell_effect == "sudden_storm":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is not None and self._is_field(state, target["location"]):
                self._deal_damage(state, target,
                                   4 if self._role(state, target) == "attacker" else 2)
                self._cleanup(state, rng)
            return True
        if implementation and implementation.spell_effect == "stun_attacking":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is not None and self._role(state, target) == "attacker":
                target["stunned"] = True
            return True
        if implementation and implementation.spell_effect == "wages_of_pain":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is not None and self._is_field(state, target["location"]):
                self._deal_damage(state, target, 3)
                self._cleanup(state, rng)
            self._play_gold_gear_token(state, owner, exhausted=True)
            return True
        if implementation and implementation.spell_effect == "buff_two_each":
            for target_id in list(item.get("targets") or [])[:2]:
                target = self._unit(state, target_id)
                if target is not None and target["owner"] == owner:
                    target["temporary"] += 1
            return True
        if implementation and implementation.spell_effect == "buff_debuff_pair":
            targets = list(item.get("targets") or [])
            if len(targets) < 2:
                return True
            first = self._unit(state, targets[0])
            second = self._unit(state, targets[1])
            if first is not None:
                first["temporary"] += 2
            if second is not None:
                second["temporary"] -= 2
            return True
        if implementation and implementation.spell_effect == "prevent_next_damage_draw":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is not None:
                target["prevent_next_damage"] = 1
            self._draw(state, owner, 1, rng)
            return True
        if implementation and implementation.spell_effect == "rally_the_troops":
            state.setdefault("rally_effects", []).append({"owner": owner, "turn": state["turn"]})
            self._draw(state, owner, 1, rng)
            return True
        if implementation and implementation.spell_effect == "ready_friendly_units":
            for unit in self._units(state, owner):
                self._ready_unit(state, unit)
            return True
        if implementation and implementation.spell_effect == "ready_friendly_and_gold":
            state["players"][owner]["ready_play"] = True
            self._play_gold_gear_token(state, owner, exhausted=True)
            return True
        if implementation and implementation.spell_effect == "draw_one_recycle_one":
            row = state["players"][owner]
            top = list(row["main"][:2])
            if not top:
                return True
            self._open_reveal(state, owner=owner, cards=top, mode="select",
                              chooser=owner, minimum=1, maximum=1,
                              effect="draw_one_recycle_one", item=item,
                              choices=top, rng=rng)
            return False
        if implementation and implementation.spell_effect == "draw_three":
            self._draw(state, owner, 3, rng)
            return True
        if implementation and implementation.spell_effect == "draw_mighty":
            amount = sum(self.might(state, unit) >= 5 for unit in self._units(state, owner))
            self._draw(state, owner, amount, rng)
            return True
        if implementation and implementation.spell_effect == "play_sand_soldier":
            self._new_unit(state, "SFD-T04", owner, f"base:{owner}")
            return True
        if implementation and implementation.spell_effect == "play_mech_token_draw":
            self._new_unit(state, "SFD-T05", owner, f"base:{owner}")
            self._draw(state, owner, 1, rng)
            return True
        if implementation and implementation.spell_effect == "return_all_units_gear":
            # Return physical cards to their owners' hands and remove token
            # objects.  This is the common return path used by ordinary
            # effects, so ownership and card conservation remain explicit.
            for unit in list(state["units"]):
                state["units"].remove(unit)
                self._hand_unit_card(state, unit)
            for row in state["players"]:
                for gear in list(row.get("gear", [])):
                    row["gear"].remove(gear)
                    self._hand_gear_card(state, gear)
            return True
        if implementation and implementation.spell_effect == "buff_five":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is not None:
                target["temporary"] += 5
            return True
        if implementation and implementation.spell_effect == "buff_two":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is not None:
                target["temporary"] += 2
            return True
        if implementation and implementation.spell_effect == "debuff_two":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is not None:
                target["temporary"] -= 2
            return True
        if implementation and implementation.spell_effect == "deathgrip":
            targets = list(item.get("targets") or [])
            if len(targets) < 2:
                return True
            killed = self._unit(state, targets[0])
            recipient = self._unit(state, targets[1])
            if (killed is None or recipient is None
                    or killed["owner"] != owner or recipient["owner"] != owner
                    or killed["id"] == recipient["id"]):
                return True
            amount = self.might(state, killed)
            state["units"].remove(killed)
            self._trash_unit_card(state, killed)
            recipient["temporary"] += amount
            self._draw(state, owner, 1, rng)
            return True
        if implementation and implementation.spell_effect == "buff_by_enemy":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is not None and target["owner"] == owner and self._is_field(state, target["location"]):
                enemy_count = len(self._units(state, 1 - owner, target["location"]))
                target["temporary"] += 2 * enemy_count
            return True
        if implementation and implementation.spell_effect == "return_gear":
            target_id = (item.get("targets") or [None])[0]
            for row in state["players"]:
                gear = next((gear for gear in row.get("gear", [])
                             if gear["id"] == target_id), None)
                if gear is not None:
                    row["gear"].remove(gear)
                    self._hand_gear_card(state, gear)
                    break
            return True
        if implementation and implementation.spell_effect == "kill_gear_draw_two":
            target_id = (item.get("targets") or [None])[0]
            for row in state["players"]:
                gear = next((gear for gear in row.get("gear", [])
                             if gear["id"] == target_id), None)
                if gear is not None:
                    row["gear"].remove(gear)
                    self._trash_gear_card(state, gear)
                    self._draw(state, gear["owner"], 2, rng)
                    break
            return True
        if implementation and implementation.spell_effect == "kill_small_unit_and_gold":
            target = self._unit(state, (item.get("targets") or [None])[0])
            if target is None or not self._is_field(state, target["location"]):
                return True
            if self.might(state, target) > 2:
                return True
            target_owner = target["owner"]
            state["units"].remove(target)
            self._trash_unit_card(state, target)
            for _ in range(2 if target_owner == owner else 1):
                self._play_gold_gear_token(state, owner, exhausted=True)
            return True
        # The Dreaming Tree trigger is generated when the spell's target was
        # chosen, before the spell resolves.  Resolve-time checks are too
        # late: a damage spell can kill the chosen friendly unit and would
        # otherwise erase the event that already happened.  The item is
        # revisited by a few multi-step spells, so mark the event once.
        if not item.get("dreaming_tree_checked"):
            item["dreaming_tree_checked"] = True
            state.setdefault("dreaming_tree_used", [False] * len(state["fields"]))
            for uid in item.get("targets", []):
                target = self._unit(state, uid)
                if (target is not None and target["owner"] == owner
                        and self._is_field(state, target["location"])
                        and state["fields"][target["location"]]["code"] == "OGN-292"
                        and not state["dreaming_tree_used"][target["location"]]):
                    state["dreaming_tree_used"][target["location"]] = True
                    self._draw(state, owner, 1, rng)
        if code == "OGN-115" and item.get("future_queue"):
            play_owner = item["future_queue"].pop(0)
            card = item["future_cards"].get(play_owner)
            if card is not None:
                row = state["players"][play_owner]
                if card in row["banishment"]:
                    row["banishment"].remove(card)
                row["hand"].append(card)
                state["chain"].append(item)
                state["actor"] = play_owner
                self._free_play_revealed_card(state, play_owner, card, item, rng,
                                              ignore_energy=True)
                if not item.get("future_queue"):
                    item["future_complete"] = True
                return False
            item["future_complete"] = True
        if code == "OGN-115" and item.get("future_complete"):
            item["future_queue"] = []
        returned = []
        killed_by_hidden_blade = None
        state.setdefault("dreaming_tree_used", [False] * len(state["fields"]))
        if code == "OGN-025" and not item.get("reveal_done"):
            opponent = 1 - owner
            top = list(state["players"][opponent]["main"][:1])
            if not top:
                return True
            self._open_reveal(state, owner=opponent, cards=top, mode="select",
                              chooser=owner, minimum=1, maximum=1,
                              effect="blind_fury", item=item, choices=top, rng=rng)
            return False
        if code == "OGN-115" and not item.get("reveal_done"):
            first = 1 - owner
            top = list(state["players"][first]["main"][:5])
            item.setdefault("future_cards", {})
            self._open_reveal(state, owner=first, cards=top, mode="select",
                              chooser=first, minimum=1 if top else 0, maximum=1,
                              effect="promising_future", item=item, choices=top, rng=rng)
            return False
        if code == "OGN-244" and not item.get("divine_done"):
            state["divine"] = {"item": item, "players": [owner, 1 - owner],
                                "index": 0, "selected": {}}
            self._open_divine_choice(state, owner)
            return False
        if code == "OGN-062" and not item.get("reveal_done"):
            top = list(state["players"][owner]["main"][:5])
            unit_choices = [uid for uid in top
                            if self.cards[state["cards"][uid]["code"]]["type"] == "unit"
                            and self._payments(
                                state, owner,
                                max(0, self.cards[state["cards"][uid]["code"]]["energy"] - 5),
                                self.cards[state["cards"][uid]["code"]]["domains"],
                                self.cards[state["cards"][uid]["code"]]["power_cost"])]
            self._open_reveal(state, owner=owner, cards=top, mode="select",
                              chooser=owner, minimum=0, maximum=1,
                              effect="reinforce", item=item, choices=unit_choices, rng=rng)
            return False
        if code == "OGN-062" and item.get("reinforce_remaining") is not None:
            remaining = [uid for uid in item.get("reinforce_remaining", [])
                         if uid in state["players"][owner]["main"]]
            item["reinforce_remaining"] = []
            self._recycle_cards_to_main(state, owner, remaining, source="main", rng=rng)
        if code == "OGN-033" and not item.get("choice_done"):
            target = self._unit(state, item.get("targets", [None])[0])
            if target is None or target["owner"] == owner:
                return True
            # Shakedown's target controller chooses whether the caster draws
            # two or the target takes six, after the spell has resolved onto
            # the Chain but before either branch is executed.
            state["decision"] = {
                "kind": "choice", "player": target["owner"],
                "options": ["draw", "damage"], "item": item,
                "shakedown": True,
            }
            state["chain"].append(item)
            state["phase"], state["actor"] = "decision", target["owner"]
            state["passes"] = 0
            return False
        if code == "OGN-071" and not item.get("choice_done"):
            state["chain"].append(item)
            state["decision"] = {"kind": "choice", "player": 1 - owner,
                                  "options": ["cards", "runes"], "item": item,
                                  "party_favors": True}
            state["phase"], state["actor"], state["passes"] = "decision", 1 - owner, 0
            return False
        if code == "OGN-187" and not item.get("choice_done"):
            state["chain"].append(item)
            state["decision"] = {"kind": "choice", "player": 1 - owner,
                                  "options": ["return", "skip"], "item": item,
                                  "whirlwind_choice": True}
            state["phase"], state["actor"], state["passes"] = "decision", 1 - owner, 0
            return False
        if code == "OGN-237" and not item.get("choice_done"):
            state["chain"].append(item)
            state["decision"] = {"kind": "target", "player": 1 - owner,
                                  "targets": [u["id"] for u in state["units"] if u["owner"] != owner],
                                  "item": item, "king_edict": True}
            state["phase"], state["actor"], state["passes"] = "decision", 1 - owner, 0
            return False
        if code == "OGN-008" and not item.get("discard_done"):
            state["chain"].append(item)
            state["decision"] = {"kind": "discard", "player": owner, "remaining": 1,
                                  "item": item, "get_excited_discard": True}
            state["phase"], state["actor"], state["passes"] = "decision", owner, 0
            return False
        if code == "OGN-266" and item.get("field") is not None:
            field = item["field"]
            for friendly in self._units(state, owner, field):
                friendly["temporary"] += 1
            for enemy in self._units(state, 1 - owner, field):
                enemy["temporary"] -= 1
        if code == "OGN-268" and item.get("field") is not None:
            for enemy in self._units(state, 1 - owner, item["field"]):
                self._deal_damage(state, enemy, int(item.get("x", 0)))
        if code == "OGN-258":
            first = self._unit(state, item.get("targets", [None])[0]) if item.get("targets") else None
            if first is None:
                return True
            if not item.get("dragon_rage_moved"):
                destination = item.get("destination")
                if destination == first["location"]:
                    return True
                self._resolve_move(state, [first], destination, owner, rng, from_effect=True)
                item["dragon_rage_moved"] = True
                candidates = [u["id"] for u in self._units(state, 1 - owner, destination)
                              if u["id"] != first["id"]]
                if not candidates:
                    return True
                state["chain"].append(item)
                state["decision"] = {"kind": "target", "player": owner,
                                      "targets": candidates, "item": item,
                                      "dragon_rage_second": True}
                state["phase"], state["actor"], state["passes"] = "decision", owner, 0
                return False
            second = self._unit(state, item.get("targets", [None, None])[1]) if len(item.get("targets", [])) > 1 else None
            if second is not None:
                self._deal_damage(state, first, self.might(state, second))
                self._deal_damage(state, second, self.might(state, first))
        if code == "OGN-256" and not item.get("fox_fire_resolution_done"):
            # Fox-Fire's group restriction is checked again after reactions.
            # If the original group is no longer legal, the controller must
            # choose a maximum-cardinality legal subset from those same targets.
            initial_ids, maximum, candidates = self._fox_fire_legal_subsets(state, item)
            if not initial_ids or maximum == 0:
                item["targets"] = []
                item["fox_fire_resolution_done"] = True
            elif maximum == len(initial_ids):
                item["targets"] = list(initial_ids)
                item["fox_fire_resolution_done"] = True
            else:
                state["chain"].append(item)
                state["decision"] = {
                    "kind": "target", "player": owner,
                    "targets": candidates, "item": item, "multi": True,
                    "min": maximum, "max": maximum, "selected": [],
                    "allow_repeat": False, "same_location": True,
                    "target_might_limit": 4, "fox_fire_resolution": True,
                }
                state["phase"], state["actor"], state["passes"] = (
                    "decision", owner, 0)
                return False
        if code == "OGN-220":
            # Facebreaker is a paired instruction: it needs one currently
            # friendly and one currently enemy unit at the same battlefield.
            # If a reaction breaks that pair, neither target is affected.
            pair = [self._unit(state, uid) for uid in item.get("targets", [])]
            friendly = next((unit for unit in pair
                             if unit is not None and unit["owner"] == owner), None)
            enemy = next((unit for unit in pair
                          if unit is not None and unit["owner"] != owner), None)
            same_field = (friendly is not None and enemy is not None
                          and self._is_field(state, friendly["location"])
                          and friendly["location"] == enemy["location"]
                          and (item.get("hidden_field") is None
                               or friendly["location"] == item["hidden_field"]))
            if same_field:
                friendly["stunned"] = True
                enemy["stunned"] = True
            item["targets"] = []

        if code == "OGN-033" and item.get("choice") == "draw":
            self._draw(state, owner, 2, rng)

        for uid in item["targets"]:
            unit = self._unit(state, uid)
            if unit is None and code == "OGN-180":
                gear = next((gear for row in state["players"] for gear in row["gear"]
                             if gear["id"] == uid), None)
                if gear is not None:
                    gear["temporary"] = True
                continue
            if unit is None or (code in {"OGN-005", "OGN-008", "OGN-009", "OGN-014",
                                          "OGN-024", "OGN-085", "OGN-169", "OGN-172",
                                          "OGN-180", "OGN-203", "OGN-213", "OGN-256", "OGN-262"}
                                and (not self._is_field(state, unit["location"])
                                     or (item.get("hidden_field") is not None
                                         and code in {"OGN-213", "OGN-256"}
                                         and unit["location"] != item["hidden_field"]))):
                continue
            if item.get("hidden_field") is not None and code in {"OGN-057", "OGN-220"} \
                    and unit["location"] != item["hidden_field"]:
                continue
            if code == "OGN-237":
                unit["damage"] = max(unit["damage"], self.might(state, unit))
            elif code == "OGN-187":
                if unit["card"] is not None:
                    state["units"].remove(unit)
                    self._hand_unit_card(state, unit)
                else:
                    unit["location"] = f"base:{unit['owner']}"
                    unit["exhausted"] = True
            elif code == "OGN-254":
                if item.get("legion"):
                    unit["damage"] = max(unit["damage"], self.might(state, unit))
                else:
                    unit["kill_on_damage"] = state["turn"]
            elif code in {"OGN-043", "OGN-173"}:
                destination = item.get("destination")
                valid_destination = (destination == f"base:{unit['owner']}" or
                                     self._is_field(state, destination))
                valid_owner = ((code == "OGN-043" and unit["owner"] != owner) or
                               (code == "OGN-173" and unit["owner"] == owner))
                if valid_destination and valid_owner and destination != unit["location"]:
                    self._resolve_move(state, [unit], destination, owner, rng,
                                       ready=code == "OGN-173", from_effect=True)
            elif code == "OGN-250":
                destination = item.get("destination")
                if (unit["owner"] == owner and unit["location"] == f"base:{owner}"
                        and self._is_field(state, destination)):
                    for enemy in list(self._units(state, 1 - owner, destination)):
                        self._deal_damage(state, enemy, self.might(state, unit))
                    self._resolve_move(state, [unit], destination, owner, rng,
                                       ready=False, from_effect=True)
            elif code == "OGN-270":
                destination = item.get("destination")
                if (unit["owner"] == owner and unit["location"] == f"base:{owner}"
                        and self._is_field(state, destination)):
                    self._apply_buff(state, unit)
                    self._resolve_move(state, [unit], destination, owner, rng,
                                       ready=False, from_effect=True)
            elif code == "OGN-102":
                self._effect_portal_rescue(state, {"owner": owner, "target": uid}, rng)
            elif code == "OGN-168":
                if self._is_field(state, unit["location"]):
                    self._resolve_move(state, [unit], f"base:{unit['owner']}", owner, rng,
                                       from_effect=True)
            elif code == "OGN-203":
                # Possession takes control first, then recalls the unit.  A
                # recall is not a move and therefore does not create a
                # Showdown; the unit arrives exhausted at the controller's
                # base with its existing damage/markers intact.
                if unit["owner"] != owner and self._is_field(state, unit["location"]):
                    # `owner` on a live unit is the current controller.  Keep
                    # the physical card owner separately so later death,
                    # recall, or recycle events return the card to its
                    # original deck rather than the new controller's zones.
                    unit.setdefault("card_owner", self._card_owner(state, unit.get("card"), unit["owner"]))
                    unit["owner"] = owner
                    unit["location"] = f"base:{owner}"
                    unit["exhausted"] = True
            elif code == "OGN-053":
                if unit["owner"] == owner:
                    state["players"][owner]["buff_bonus"] = 1
                    self._apply_buff(state, unit)
            elif code == "OGN-069":
                # Last Stand doubles the unit's current Might for this turn;
                # the temporary marker is removed at the next Beginning Phase.
                if unit["owner"] == owner:
                    unit["temporary"] += self.might(state, unit)
                    unit["temporary_unit"] = True
            elif code == "OGN-180":
                gear = next((gear for row in state["players"] for gear in row["gear"]
                             if gear["id"] == uid), None)
                if gear is not None:
                    gear["temporary"] = True
                else:
                    unit["temporary_unit"] = True
            elif code in {"OGN-206", "OGN-207"}:
                if code != "OGN-206" or unit["owner"] == owner:
                    unit["temporary"] += 2 if code == "OGN-206" else 3
            elif code == "OGN-008":
                discarded = item.get("discarded_card")
                if discarded is not None:
                    self._deal_damage(state, unit,
                                      self.cards[state["cards"][discarded]["code"]]["energy"])
            elif code == "OGN-004":
                unit["assault"] += 3
            elif code == "OGN-014":
                self._deal_damage(state, unit, 5)
            elif code in {"OGN-005", "OGN-009", "OGN-024", "OGN-029", "OGN-085"}:
                self._deal_damage(state, unit, {"OGN-005": 3, "OGN-009": 3, "OGN-024": 4,
                                                "OGN-029": 3, "OGN-085": 6}[code])
            elif code == "OGN-105":
                self._deal_damage(state, unit, 6)
            elif code == "OGN-248":
                self._deal_damage(state, unit, 2)
            elif code in {"OGN-229", "OGN-256"}:
                unit["damage"] = max(unit["damage"], self.might(state, unit))
            elif code == "OGN-057":
                unit["combat_shield"] = 3
                unit["temporary_tank"] = True
            elif code == "OGN-093":
                unit["temporary"] -= 4
            elif code == "OGN-095":
                unit["temporary"] -= 1
            elif code == "OGN-050":
                unit["stunned"] = True
            elif code == "OGN-058":
                unit["temporary"] += 2
            elif code == "OGN-154":
                unit["temporary"] += 7
            elif code == "OGN-046":
                if unit["owner"] == owner:
                    unit["temporary"] += 1
                    if len(self._units(state, owner, unit["location"])) == 1:
                        unit["temporary"] += 1
            elif code in {"OGN-104", "OGN-169", "OGN-172"}:
                if code != "OGN-169" or self.might(state, unit) <= 3:
                    returned.append(unit)
            elif code == "OGN-213":
                killed_by_hidden_blade = unit["owner"]
                unit["damage"] = max(unit["damage"], self.might(state, unit))
            elif code == "OGN-220":
                unit["stunned"] = True
            elif code == "OGN-146":
                self._ready_unit(state, unit)
            elif code == "OGN-252":
                self._deal_damage(state, unit, 5)
            elif code == "OGN-033":
                if item.get("choice") == "damage" and unit["owner"] != owner:
                    self._deal_damage(state, unit, 6)
            elif code == "OGN-262":
                if unit["owner"] != owner and self._is_field(state, unit["location"]):
                    unit["stunned"] = True
            elif code == "OGN-266" and item.get("field") is None:
                field = unit["location"]
                for friendly in self._units(state, owner, field):
                    friendly["temporary"] += 1
                for enemy in self._units(state, 1-owner, field):
                    enemy["temporary"] -= 1
            elif code == "OGN-108" and item["targets"] and item["targets"][0] == uid:
                if unit["owner"] == owner and len(item["targets"]) >= 2:
                    other = self._unit(state, item["targets"][1])
                    if other is not None and other["owner"] == owner:
                        unit["temporary"] += self.might(state, other) - self.might(state, unit)
            elif code == "OGN-128" and item["targets"] and item["targets"][0] == uid and len(item["targets"]) >= 2:
                other = self._unit(state, item["targets"][1])
                if unit["owner"] == owner and other is not None and other["owner"] != owner:
                    self._deal_damage(state, unit, self.might(state, other))
                    self._deal_damage(state, other, self.might(state, unit))
            elif code == "OGN-209":
                unit["damage"] = max(unit["damage"], self.might(state, unit))
            elif code == "OGN-260" and item["targets"] and item["targets"][0] == uid and len(item["targets"]) >= 2:
                other = self._unit(state, item["targets"][1])
                if unit["owner"] == owner:
                    self._ready_unit(state, unit)
                if (unit["owner"] == owner and other is not None
                        and other["owner"] != owner
                        and self._is_field(state, other["location"])):
                    self._deal_damage(state, other, self.might(state, unit))
        for unit in returned:
            if unit not in state["units"]:
                continue
            state["units"].remove(unit)
            card = unit["card"]
            if card is not None:
                row = state["players"][self._unit_card_owner(state, unit)]
                if card in row["champion"]:
                    row["champion"].remove(card)
                self._hand_unit_card(state, unit)
            if code == "OGN-104":
                self._channel_rune(state, unit["owner"], exhausted=True)
        if code == "OGN-048":
            drawn = False
            if item["targets"]:
                target = self._unit(state, item["targets"][0])
                if target is not None and target["owner"] == owner and not target["exhausted"]:
                    target["exhausted"] = True
                    drawn = True
            self._draw(state, owner, 2 if drawn else 1, rng)
        elif code == "OGN-144":
            self._draw(state, owner, 2, rng)
        elif code == "OGN-224":
            self._draw(state, owner, 1, rng)
        elif code == "OGN-198":
            row = state["players"][owner]
            candidates = []
            for uid in row["trash"]:
                data = self.cards[state["cards"][uid]["code"]]
                if data["type"] == "unit" and self._payments(
                        state, owner, 0, data["domains"], data["power_cost"]):
                    candidates.append(uid)
            if candidates:
                self._open_reveal(state, owner=owner, cards=candidates,
                                  mode="select", chooser=owner, minimum=0,
                                  maximum=1, effect="harrowing_play", item=item,
                                  choices=candidates, rng=rng)
                return False
        elif code == "OGN-022":
            for player in (0, 1):
                for gear in list(state["players"][player]["gear"]):
                    state["players"][player]["gear"].remove(gear)
                    self._trash_gear_card(state, gear)
        elif code == "OGN-179":
            for player in (0, 1):
                gears = state["players"][player]["gear"]
                if gears:
                    self._trash_gear_card(state, gears.pop(0))
        elif code == "OGN-145":
            state["prevent_spell_ability_damage"] = True
        elif code == "OGN-122":
            state["extra_turn"] = owner
        elif code == "OGN-153":
            for unit in self._units(state, owner):
                if unit["buff"]:
                    unit["buff"] = 0
                    self._ready_unit(state, unit)
            for unit in self._units(state, owner):
                self._apply_buff(state, unit)
        elif code == "OGN-094":
            token = self._new_unit(state, SPRITE_TOKEN, owner, f"base:{owner}", exhausted=False)
            token["temporary_unit"] = True
        elif code == "OGN-123":
            for friendly in self._units(state, owner):
                friendly["exhausted"] = True
            for field in range(len(state["fields"])):
                for unit in self._units(state, location=field):
                    self._deal_damage(state, unit, 12)
        elif code == "OGN-138":
            channeled = sum(self._channel_rune(state, owner, exhausted=True) for _ in range(2))
            if channeled < 2:
                self._draw(state, owner, 1, rng)
        elif code == "OGN-047":
            self._draw(state, owner, 1, rng)
            self._channel_rune(state, owner)
        elif code == "OGN-183":
            # Stacked Deck's top three are captured when the target window is
            # opened.  The chosen card goes to hand and the other revealed
            # cards are recycled in their current order.
            row = state["players"][owner]
            options = [uid for uid in item.get("deck_options", []) if uid in row["main"]]
            chosen = item.get("targets", [None])[0] if item.get("targets") else None
            if chosen not in options:
                chosen = options[0] if options else None
            if chosen is not None:
                row["main"].remove(chosen)
                row["hand"].append(chosen)
                self._recycle_cards_to_main(
                    state, owner, [uid for uid in options if uid != chosen],
                    source="main", rng=rng)
        elif code == "OGN-221":
            # Until end of the current turn, any later damage marks its unit
            # lethal; ordinary cleanup then performs the kill and triggers.
            state["imperial_decree"] = {"owner": owner, "turn": state["turn"]}
        elif code == "OGN-134":
            if not self._channel_rune(state, owner, exhausted=True):
                self._draw(state, owner, 1, rng)
        elif code == "OGN-233":
            for unit in self._units(state, owner):
                unit["temporary"] += 5
        elif code == "OGN-264" and not item.get("reveal_done"):
            row = state["players"][owner]
            choices = [uid for uid in row["trash"]
                       if self._is_hidden_code(state["cards"][uid]["code"])]
            self._open_reveal(state, owner=owner, cards=list(choices), mode="select",
                              chooser=owner, minimum=0, maximum=min(2, len(choices)),
                              effect="guerrilla_return_hidden", item=item,
                              choices=list(choices), rng=rng)
            return False
        if code == "OGN-071":
            option = item.get("choice")
            if option == "cards":
                self._draw(state, owner, 1, rng)
                self._draw(state, 1 - owner, 1, rng)
            elif option == "runes":
                self._channel_rune(state, owner, exhausted=True)
                self._channel_rune(state, 1 - owner, exhausted=True)
        elif code == "OGN-268" and item.get("field") is None:
            destination = item.get("destination")
            for enemy in list(self._units(state, 1 - owner, destination)):
                self._deal_damage(state, enemy, int(item.get("x", 0)))
        if code == "OGN-127" and state["battle"] is not None:
            field = state["battle"]["field"]
            for unit in self._units(state, location=field):
                if unit["owner"] != owner:
                    self._deal_damage(state, unit, 2)
        elif code == "OGN-133":
            for unit in self._units(state):
                if self._is_field(state, unit["location"]):
                    self._deal_damage(state, unit, 1)
        target_ids = set(item["targets"])
        self._cleanup(state, rng)
        killed = any(uid not in {u["id"] for u in state["units"]} for uid in target_ids)
        if code == "OGN-213" and killed and killed_by_hidden_blade is not None:
            self._draw(state, killed_by_hidden_blade, 2, rng)
        if code == "OGN-129":
            state["players"][owner]["ready_play"] = True
            self._draw(state, owner, 1, rng)
        elif code == "OGN-083":
            self._draw(state, owner, 2, rng)
        elif code == "OGN-114":
            self._draw(state, owner, 4, rng)
        elif code == "OGN-201":
            for player in (0, 1):
                trash = state["players"][player]["trash"]
                discarded = bool(state["players"][player]["hand"])
                trash.extend(state["players"][player]["hand"])
                state["players"][player]["hand"] = []
                if discarded:
                    state["players"][player]["discarded_this_turn"] = True
                    self._trigger_jinx_discard(state, player)
                self._draw(state, player, 4, rng)
        elif code in {"OGN-024", "OGN-058", "OGN-095"} or (code == "OGN-005" and killed):
            if state["winner"] is None:
                self._draw(state, owner, 1, rng)
        if code == "OGN-122":
            state["players"][self._card_owner(state, item.get("card"), owner)]["banishment"].append(item["card"])
        else:
            self._trash_card(state, item.get("card"), owner)
        if code == "OGN-008" and item.get("discarded_card") is not None:
            self._trigger_jinx_discard(state, owner)
        if item.get("recycle_after"):
            physical_owner = self._card_owner(state, item.get("card"), owner)
            self._recycle_cards_to_main(state, physical_owner, [item["card"]], source="trash", rng=rng)
        return True

    def apply(self, state, action, rng):
        kind, args = action.kind, json.loads(action.arguments)
        player = state["actor"]
        row = state["players"][player]
        # Rune rollback is intentionally a narrow transaction: any decision,
        # pass, card play, movement, or other action closes the rollback
        # window. Consecutive rune resource actions are the only exception.
        if kind not in {"exhaust_rune", "recycle_rune", "undo_rune"}:
            state["rune_undo"] = []
        if state.get("phase") == "reveal":
            reveal = state.get("reveal")
            if reveal is None:
                raise ValueError("no reveal window is active")
            if kind == "end_reveal":
                if reveal["kind"] != "display" or player != reveal["closer"]:
                    raise ValueError("only the displayed player's opponent can end this reveal")
                if reveal.get("effect") == "dazzling_aurora":
                    self._finish_reveal(state, [], rng)
                    return
                if reveal.get("effect") == "apprentice_smith":
                    self._finish_reveal(state, [], rng)
                    return
                if reveal.get("effect") == "mindsplitter":
                    # The opponent closes the public reveal; the caster then
                    # chooses one of the revealed physical hand cards.  Keep
                    # the chain item pending until that choice is confirmed.
                    item = reveal.get("item") or {}
                    state["reveal"] = None
                    state["decision"] = {
                        "kind": "hand_card", "player": item.get("owner"),
                        "cards": list(reveal.get("cards", [])),
                        "item": item, "mindsplitter": True,
                    }
                    state["phase"], state["actor"], state["passes"] = (
                        "decision", item.get("owner"), 0)
                    return
                # A display-only effect still has to complete the card that
                # opened the window (including post-spell triggers).  The
                # chain resolver had popped that item before opening the
                # reveal, so put it back on top and mark the reveal complete.
                item = reveal.get("item")
                if reveal.get("effect") == "teemo_defend":
                    owner = reveal["owner"]
                    top = [uid for uid in reveal.get("cards", [])
                           if uid in state["players"][owner]["main"]]
                    item["hidden_count"] = sum(
                        self._is_hidden_code(state["cards"][uid]["code"]) for uid in top)
                    self._recycle_cards_to_main(state, owner, top, source="main", rng=rng)
                if item is not None and reveal.get("resume", {}).get("phase") == "chain":
                    item["reveal_done"] = True
                    state["chain"].append(item)
                resume = reveal["resume"]
                state["reveal"] = None
                if resume["phase"] == "chain":
                    state["phase"], state["actor"], state["passes"] = "chain", resume["actor"], 0
                    self._finish_resolution(state)
                else:
                    state["phase"], state["actor"], state["passes"] = resume["phase"], resume["actor"], resume.get("passes", 0)
                self._cleanup(state, rng)
                return
            if kind == "order_revealed":
                if reveal["kind"] != "reorder" or player != reveal["chooser"]:
                    raise ValueError("reveal ordering is unavailable")
                order = list(args.get("order", []))
                cards = list(reveal.get("cards", []))
                if len(order) != len(cards) or set(order) != set(cards):
                    raise ValueError("invalid retained-card order")
                # Restore the original two-card selection and let the normal
                # reveal finalizer perform recycling, Karma triggers, and
                # chain resumption in one place.
                selected = list(reveal.get("recycle_selected", []))
                reveal["kind"] = "select"
                reveal["cards"] = list(reveal.get("original_cards", cards))
                reveal["choices"] = list(reveal["cards"])
                reveal["selected"] = selected
                reveal["ordered"] = True
                reveal["ordered_cards"] = order
                self._finish_reveal(state, selected, rng)
                return
            if kind == "choose_revealed":
                if reveal["kind"] != "select" or player != reveal["chooser"]:
                    raise ValueError("reveal selection is unavailable")
                card = args["card"]
                if card not in reveal["cards"] or card in reveal["selected"]:
                    raise ValueError("invalid revealed card")
                if len(reveal["selected"]) >= reveal["max"]:
                    raise ValueError("too many revealed cards selected")
                reveal["selected"].append(card)
                return
            if kind == "confirm_revealed":
                if reveal["kind"] != "select" or player != reveal["chooser"]:
                    raise ValueError("reveal selection is unavailable")
                if len(reveal["selected"]) < reveal["min"]:
                    raise ValueError("not enough revealed cards selected")
                self._finish_reveal(state, list(reveal["selected"]), rng)
                return
            raise ValueError("invalid reveal action")
        if kind in {"choose_divine", "confirm_divine"}:
            decision = state.get("decision")
            if not decision or decision.get("kind") != "divine" or player != decision.get("player"):
                raise ValueError("Divine Judgment choice is unavailable")
            if kind == "choose_divine":
                zone, card = args.get("zone"), args.get("card")
                choices = decision.get("choices", {}).get(zone, [])
                selected = decision.setdefault("selected", {}).setdefault(zone, [])
                if card not in choices:
                    raise ValueError("invalid Divine Judgment selection")
                if card in selected:
                    selected.remove(card)
                elif len(selected) >= 2:
                    raise ValueError("Divine Judgment allows at most two cards per zone")
                else:
                    selected.append(card)
                state["passes"] = 0
                return
            if any(len(decision.get("selected", {}).get(zone, [])) < need
                   for zone, need in decision.get("required", {}).items()):
                raise ValueError("Divine Judgment requires two selections per available zone")
            self._finish_divine_choice(state, player, rng)
            return
        if kind == "ability_activate":
            spec = self.abilities.get(args.get("ability_id"))
            if not spec.copyable:
                raise ValueError("ability is not copyable by Heimerdinger")
            snapshot = copy.deepcopy(state)
            try:
                self._resolve_registry_copy(state, player, args, rng)
            except Exception:
                state.clear()
                state.update(snapshot)
                raise
            state["passes"] = 0
            return
        if kind == "ability_targeted":
            spec = self.abilities.get(args.get("ability_id"))
            if not spec.copyable:
                raise ValueError("ability is not copyable by Heimerdinger")
            source = self._unit(state, args.get("source"))
            if source is None or source["owner"] != player or source["code"] != "OGN-111" or source["exhausted"]:
                raise ValueError("copied ability source is unavailable")
            if not self._registry_copy_available(state, player, source, spec):
                raise ValueError("copied ability is unavailable at this timing")
            state["decision"] = {"kind": "target", "player": player,
                                  "targets": list(args.get("target_candidates", [])),
                                  "item": {"registry_copy": True, "ability_id": spec.ability_id,
                                           "source": source["id"], "origin": args.get("origin"),
                                           "copied_from": args.get("copied_from"), "owner": player},
                                  "registry_ability": True}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return
        if kind == "choose_field":
            decision = state.get("decision")
            field = args.get("field")
            if (decision and decision.get("kind") == "field_multi"
                    and player == decision.get("player")
                    and field in decision.get("fields", [])):
                selected = decision.setdefault("selected", [])
                selected.append(field)
                if len(selected) < int(decision.get("remaining", 0)):
                    state["passes"] = 0
                    return
                item = decision["item"]
                gear = next((g for g in row["gear"] if g["id"] == item["gear"]), None)
                if gear is None or gear["exhausted"]:
                    raise ValueError("token-producing gear is no longer available")
                gear["exhausted"] = True
                self._gear_ability_used(state, player)
                for destination in selected:
                    self._new_unit(state, TOKEN, player, destination)
                state["decision"] = None
                state["phase"], state["actor"], state["passes"] = "main", player, 0
                self._cleanup(state, rng)
                return
            if (not decision or decision.get("kind") != "field"
                    or field not in decision.get("fields", [])):
                raise ValueError("field target selection is unavailable")
            if decision.get("free_play_field"):
                info = dict(decision["free_play_field"])
                info["field"] = field
                if decision.get("x_choice"):
                    state["decision"] = {
                        "kind": "choice", "player": player,
                        "options": list(range(decision.get("x_max", 0) + 1)),
                        "x_choice": True, "free_play_field": info,
                    }
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
                else:
                    self._complete_free_play_field(state, info, rng)
                return
            item = decision["item"]
            item["field"] = field
            if decision.get("x_choice"):
                state["decision"] = {"kind": "choice", "player": player,
                                      "options": list(range(decision.get("x_max", 0) + 1)),
                                      "item": item, "x_choice": True,
                                      "counter_retarget": decision.get("counter_retarget", False)}
                state["phase"], state["actor"], state["passes"] = "decision", player, 0
                return
            self._mark_play_finalized(
                state, item.get("played_by", item["owner"]),
                item.get("card"), item=item)
            state["decision"] = None
            state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
            return
        if kind == "choose_chain_target":
            decision = state.get("decision")
            target = args.get("target")
            if not decision or decision.get("kind") != "chain_target" or target not in decision.get("targets", []):
                raise ValueError("chain target selection is unavailable")
            item = decision["item"]
            item["counter_target"] = target
            played_by = item.get("played_by", item["owner"])
            if "post_triggers" not in item:
                item["post_triggers"] = self._spell_post_triggers(
                    state, played_by, self._played_for_legion(state, played_by) > 0)
            self._mark_play_finalized(state, played_by, item.get("card"), item=item)
            state["decision"] = None
            state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
            return
        if kind in {"predict", "discard_card", "choose_target", "confirm_targets", "cancel_play", "choose_option", "choose_card", "choose_payment"}:
            if kind == "choose_payment":
                decision = state.get("decision")
                payment = list(args.get("payment", []))
                if (not decision or decision.get("kind") != "free_play_payment"
                        or player != decision.get("player")
                        or payment not in [list(option) for option in decision.get("payments", [])]):
                    raise ValueError("free-play payment choice is unavailable")
                if "free_play_spell" in decision:
                    info = dict(decision["free_play_spell"])
                    info["payment"] = payment
                    self._complete_free_play_target(
                        state, {"free_play": info},
                        list(info.get("selected", decision.get("targets", []))), rng)
                    return
                if "free_play_field" in decision:
                    info = dict(decision["free_play_field"])
                    info["payment"] = payment
                    # The battlefield was already selected before this
                    # payment window; continue directly rather than forcing
                    # the player to click the same field again.
                    self._complete_free_play_field(state, info, rng)
                    return
                if "free_play_gear" in decision:
                    info = dict(decision["free_play_gear"])
                    owner, card = info["owner"], info["card"]
                    physical = state["players"][info.get("card_owner", owner)]
                    row = state["players"][owner]
                    if card in physical.get("banishment", []):
                        physical["banishment"].remove(card)
                    if card not in row["hand"]:
                        row["hand"].append(card)
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", owner, 0
                    self.apply(state, Action.make(
                        "play_gear", card=card, payment=payment,
                        ignore_cost=bool(info.get("free_all")),
                        card_owner=info.get("card_owner"),
                        ignore_energy=bool(info.get("ignore_energy")),
                        free_play_parent=True), rng)
                    parent = info.get("parent")
                    if (parent is not None and parent in state.get("chain", [])
                            and state.get("phase") == "main"):
                        state["phase"], state["actor"] = "chain", state["chain"][-1]["owner"]
                    return
                info = dict(decision["free_play_unit"])
                info["payment"] = payment
                if not decision.get("targets"):
                    owner = info["owner"]
                    card = info["card"]
                    physical = state["players"][info.get("card_owner", owner)]
                    row = state["players"][owner]
                    if card in physical.get("banishment", []):
                        physical["banishment"].remove(card)
                    if card not in row["hand"]:
                        row["hand"].append(card)
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", owner, 0
                    self.apply(state, Action.make(
                        "play_unit", card=card, location=f"base:{owner}",
                        accelerate=False, payment=payment, enter_target=None,
                        ignore_cost=((not info.get("ignore_energy")
                                      and not info.get("energy_reduction"))
                                     or bool(info.get("free_all"))),
                        ignore_energy=bool(info.get("ignore_energy")) or bool(info.get("free_all")),
                        energy_reduction=int(info.get("energy_reduction", 0)),
                        free_play_parent=True), rng)
                    parent = info.get("parent")
                    if (parent is not None and parent in state.get("chain", [])
                            and state.get("phase") == "main"):
                        state["phase"], state["actor"] = "chain", state["chain"][-1]["owner"]
                    return
                if info.get("enter_target") is not None:
                    self._complete_free_play_unit_target(
                        state, info, info["enter_target"], rng,
                        payment_override=payment)
                    return
                state["decision"] = {
                    "kind": "target", "player": player,
                    "targets": list(decision.get("targets", [])),
                    "item": info.get("parent"),
                    "free_play_unit": info,
                }
                state["phase"], state["actor"], state["passes"] = "decision", player, 0
                return
            if kind == "choose_option":
                decision = state.get("decision")
                if not decision or decision.get("kind") != "choice" or args.get("option") not in decision.get("options", []):
                    raise ValueError("invalid choice option")
                option = args["option"]
                if decision.get("free_play_field"):
                    info = dict(decision["free_play_field"])
                    x = int(option)
                    if x < 0 or x > len(row.get("power", [])):
                        raise ValueError("invalid free-play X payment")
                    info["x"] = x
                    self._complete_free_play_field(state, info, rng)
                    return
                if decision.get("free_play_buff"):
                    info = dict(decision["free_play_buff"])
                    options = info.get("payment_options", {})
                    if option not in options:
                        raise ValueError("invalid free-play resource choice")
                    choices = [list(choice) for choice in options[option]]
                    spend_buff = None if option == "power" else option.split(":", 1)[1]
                    info.pop("payment_options", None)
                    info["spend_buff"] = spend_buff
                    if len(choices) > 1:
                        state["decision"] = {
                            "kind": "free_play_payment", "player": player,
                            "payments": choices, "targets": list(info.get("selected", [])),
                            "free_play_spell": {**info, "payment": None},
                        }
                        state["phase"], state["actor"], state["passes"] = "decision", player, 0
                        return
                    info["payment"] = choices[0]
                    self._complete_free_play_target(
                        state, {"free_play": info}, list(info.get("selected", [])), rng)
                    return
                if decision.get("nocturne_reveal"):
                    reveal = state.get("reveal")
                    card = decision["nocturne_reveal"]["card"]
                    owner = decision["nocturne_reveal"]["owner"]
                    row = state["players"][owner]
                    if option == "nocturne_skip":
                        self._resume_reveal_after_nocturne(state)
                        return
                    if option == "nocturne_banish":
                        if card not in row["main"]:
                            raise ValueError("Nocturne is no longer in the revealed deck segment")
                        row["main"].remove(card)
                        row["banishment"].append(card)
                        aurora_stop = decision["nocturne_reveal"].get("aurora_stop", False)
                        if reveal is not None and card in reveal.get("cards", []) and not aurora_stop:
                            reveal["cards"].remove(card)
                        if reveal is not None and card in reveal.get("choices", []):
                            reveal["choices"].remove(card)
                        if reveal is not None and aurora_stop:
                            reveal["aurora_nocturne_banished"] = card
                        state["decision"] = {
                            "kind": "choice", "player": owner,
                            "options": ["nocturne_play", "nocturne_leave"],
                            "nocturne_play": {"card": card, "owner": owner,
                                               "aurora_stop": aurora_stop},
                        }
                        return
                    raise ValueError("invalid Nocturne replacement choice")
                if decision.get("nocturne_play"):
                    card = decision["nocturne_play"]["card"]
                    owner = decision["nocturne_play"]["owner"]
                    row = state["players"][owner]
                    if option == "nocturne_leave":
                        if decision["nocturne_play"].get("aurora_stop"):
                            reveal = state.get("reveal")
                            if reveal is not None and reveal.get("item") is not None:
                                reveal["item"]["advance_gear"] = True
                            self._finish_reveal(state, [], rng)
                            return
                        self._resume_reveal_after_nocturne(state)
                        return
                    if option != "nocturne_play":
                        raise ValueError("invalid Nocturne play choice")
                    payment = self._payments(state, owner, 0, DOMAINS, 0, 1)
                    if not payment:
                        raise ValueError("Nocturne requires one rainbow power")
                    self._pay(row, 0, payment[0])
                    if card not in row["banishment"]:
                        raise ValueError("Nocturne is no longer in Banishment")
                    row["banishment"].remove(card)
                    row["hand"].append(card)
                    if decision["nocturne_play"].get("aurora_stop"):
                        reveal = state.get("reveal")
                        parent = reveal.get("item") if reveal is not None else {
                            "effect": "dazzling_aurora_continue", "owner": owner}
                        parent["advance_gear"] = True
                        state["decision"] = None
                        state["reveal"] = None
                        state["phase"], state["actor"], state["passes"] = "chain", owner, 0
                        self._free_play_revealed_card(
                            state, owner, card, parent, rng, free_all=True,
                            card_owner=owner)
                        return
                    self.apply(state, Action.make("play_unit", card=card,
                                                  location=f"base:{owner}", accelerate=False,
                                                  payment=[], enter_target=None,
                                                  ignore_cost=True, ignore_energy=True,
                                                  free_play_parent=True), rng)
                    self._resume_reveal_after_nocturne(state)
                    return
                if decision.get("nocturne"):
                    nocturne = decision["nocturne"]
                    if option == "nocturne_skip":
                        state["decision"] = {"kind": "predict", "player": player, "remaining": 1}
                        return
                    if option != "nocturne_banish":
                        raise ValueError("invalid Nocturne choice")
                    payment = self._payments(state, player, 0, DOMAINS, 0, 1)
                    if not payment:
                        raise ValueError("Nocturne requires one rainbow power")
                    self._pay(row, 0, payment[0])
                    card = nocturne["card"]
                    if card not in row["main"]:
                        raise ValueError("Nocturne is no longer on top of the deck")
                    row["main"].remove(card)
                    row["banishment"].append(card)
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", player, 0
                    self._free_play_revealed_card(state, player, card, nocturne["item"], rng, free_all=True)
                    return
                if decision.get("x_choice"):
                    item = decision["item"]
                    x = int(option)
                    if x < 0 or x > len(row["power"]):
                        raise ValueError("invalid X payment")
                    if not decision.get("counter_retarget"):
                        self._pay(row, 0, list(range(x)))
                    item["x"] = x
                    if decision.get("item", {}).get("effect") == "spell":
                        self._mark_play_finalized(
                            state, item.get("played_by", item["owner"]),
                            item.get("card"), item=item)
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("destination_choice"):
                    if decision.get("free_play"):
                        info = decision["free_play"]
                        info["destination"] = option
                        self._complete_free_play_target(state, decision,
                                                        [decision["free_play_target"]], rng)
                        return
                    item = decision["item"]
                    if item.get("registry_copy"):
                        target = self._unit(state, item.get("target"))
                        if target is None:
                            raise ValueError("copied move target unavailable")
                        self._resolve_move(state, [target], option, player, rng, from_effect=True)
                        state["decision"] = None
                        state["phase"], state["actor"], state["passes"] = "main", player, 0
                        self._cleanup(state, rng)
                        return
                    if item.get("legend_move"):
                        state["decision"] = None
                        state["phase"], state["actor"], state["passes"] = "main", player, 0
                        self.apply(state, Action.make("legend_move", target=item["target"],
                                                       destination=option), rng)
                        return
                    item["destination"] = option
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("accelerate"):
                    pending = decision["accelerate"]
                    unit = self._unit(state, pending["unit"])
                    if unit is None or unit["owner"] != player:
                        raise ValueError("Accelerate unit is no longer in play")
                    if option == "accelerate":
                        row = state["players"][player]
                        domains = set(pending.get("domains", []))
                        if len(domains) == 1:
                            power_index = next((index for index, power in enumerate(row["power"])
                                                if power in domains or power == "any"), None)
                        else:
                            power_index = 0 if row["power"] else None
                        if row["energy"] < 1 or power_index is None:
                            raise ValueError("Accelerate requires 1 energy and one matching domain power")
                        row["energy"] -= 1
                        row["power"].pop(power_index)
                        # 805.6: the replacement makes the unit enter ready;
                        # this is not a separate 'becomes ready' event.
                        # Accelerate is a play-time replacement, not a
                        # separate "becomes ready" event.
                        unit["exhausted"] = False
                    state["decision"] = None
                    self._finish_unit_play(state, pending, rng)
                    if pending.get("resume_chain") and state.get("chain") and state.get("phase") == "main":
                        state["phase"], state["actor"], state["passes"] = "chain", state["chain"][-1]["owner"], 0
                    return
                if decision.get("udyr_choice"):
                    item = decision["item"]
                    option = args["option"]
                    source = self._unit(state, item["source"])
                    if source is None:
                        raise ValueError("Udyr source is unavailable")
                    if option in {"damage", "stun"}:
                        state["decision"] = {"kind": "target", "player": player,
                                              "targets": [u["id"] for u in state["units"]
                                                          if self._is_field(state, u["location"])],
                                              "item": item, "udyr_option": option}
                        item["option"] = option
                        return
                    if option == "ready":
                        self._ready_unit(state, source)
                    elif option == "ganking":
                        source["temporary_ganking"] = True
                    source.setdefault("udyr_choices", []).append(option)
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "main", player, 0
                    self._cleanup(state, rng)
                    if state.get("decision") is None and state.get("reveal") is None:
                        self._flush_deferred_battlefield_optionals(state)
                    return
                if decision.get("legend_toggle"):
                    if option not in {"ready", "exhaust"}:
                        raise ValueError("invalid legend state choice")
                    row = state["players"][player]
                    row["legend_exhausted"] = option == "exhaust"
                    item = decision.get("item")
                    state["decision"] = None
                    self._finish_resolution(state)
                    return
                if decision.get("draw_or_buff"):
                    if option not in {"draw", "buff"}:
                        raise ValueError("invalid draw or buff choice")
                    item = decision.get("item", {})
                    source = self._unit(state, item.get("source"))
                    if option == "draw":
                        self._draw(state, player, 1, rng)
                    elif source is not None and source["owner"] == player:
                        self._apply_buff(state, source)
                    state["decision"] = None
                    restored = state.pop("optional_return", None)
                    state["optional_ordered"] = False
                    if state.get("optional"):
                        state["phase"], state["actor"] = "optional", state["optional"][0]["player"]
                        state["passes"] = 0
                    elif restored is None:
                        state["phase"], state["actor"], state["passes"] = "main", player, 0
                    elif restored["phase"] == "chain" and not state.get("chain"):
                        self._finish_resolution(state)
                    else:
                        state["phase"], state["actor"], state["passes"] = (
                            restored["phase"], restored["actor"], restored.get("passes", 0))
                    self._cleanup(state, rng)
                    return
                if decision.get("counter_retarget_choice"):
                    item = decision["item"]
                    if option not in decision.get("options", []):
                        raise ValueError("invalid Mystic Reversal choice")
                    if item.get("code") == "OGN-187" and option == "return":
                        state["decision"] = {
                            # The same player who made Whirlwind's option
                            # choice chooses the unit to return.
                            "kind": "target", "player": player,
                            "targets": [u["id"] for u in state["units"]],
                            "item": item, "whirlwind_target": True,
                            "counter_retarget": True,
                        }
                        state["phase"], state["actor"], state["passes"] = (
                            "decision", player, 0)
                        return
                    item["choice"] = option
                    item["choice_done"] = True
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("party_favors"):
                    item = decision["item"]
                    item["choice"] = option
                    item["choice_done"] = True
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("shakedown"):
                    if option not in {"draw", "damage"}:
                        raise ValueError("invalid Shakedown choice")
                    item = decision["item"]
                    item["choice"] = option
                    item["choice_done"] = True
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("whirlwind_choice"):
                    item = decision["item"]
                    if option == "skip":
                        item["choice_done"] = True
                        state["decision"] = None
                        state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    else:
                        state["decision"] = {"kind": "target", "player": player,
                                              "targets": [u["id"] for u in state["units"]],
                                              "item": item, "whirlwind_target": True}
                    return
                if option == "draw":
                    self._draw(state, player, 1, rng)
                elif option == "channel":
                    self._channel_rune(state, player, exhausted=True)
                state["decision"] = None
                restored = state.pop("optional_return", None)
                state["optional_ordered"] = False
                if restored is None:
                    state["phase"], state["actor"], state["passes"] = "main", state["turn_player"], 0
                else:
                    state["phase"], state["actor"], state["passes"] = restored["phase"], restored["actor"], restored.get("passes", 0)
                self._cleanup(state, rng)
                return
            elif kind == "predict":
                if args["recycle"] and row["main"]:
                    self._recycle_cards_to_main(state, player, [row["main"][0]],
                                                source="main", rng=rng)
                state["decision"] = None
            elif kind == "discard_card":
                decision = state["decision"]
                row["hand"].remove(args["card"])
                row["trash"].append(args["card"])
                row["discarded_this_turn"] = True
                if decision.get("undercover_discard"):
                    decision["remaining"] -= 1
                    if decision["remaining"]:
                        return
                    self._finish_undercover_discard(state, rng)
                    return
                if decision.get("scrapyard_discard"):
                    decision["remaining"] -= 1
                    if decision["remaining"]:
                        return
                    self._draw(state, player, 2, rng)
                    post = decision.get("post_triggers", [])
                    self._mark_play_finalized(state, player, decision.get("finalized_card"),
                                              trigger_sink=post, rng=rng)
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "main", player, 0
                    self._cleanup(state, rng)
                    self._trigger_jinx_discard(state, player)
                    self._triggers(state, post)
                    return
                if decision.get("get_excited_discard"):
                    item = decision["item"]
                    item["discarded_card"] = args["card"]
                    item["discard_done"] = True
                    targets = [u["id"] for u in state["units"]
                               if self._is_field(state, u["location"])]
                    if targets:
                        state["decision"] = {"kind": "target", "player": player,
                                              "targets": targets, "item": item,
                                              "get_excited_target": True}
                        state["phase"], state["actor"], state["passes"] = "decision", player, 0
                    else:
                        state["decision"] = None
                        state["phase"], state["actor"], state["passes"] = "chain", player, 0
                    return
                if decision.get("discard_one_draw_two"):
                    self._draw(state, player, 2, rng)
                    item = decision.get("item")
                    state["decision"] = None
                    self._finish_resolution(state)
                    self._trigger_jinx_discard(state, player)
                    return
                if decision.get("zaun_warrens"):
                    state["decision"] = None
                    # The score helper starts this choice from Main after the
                    # battle has already closed.  Restore that context before
                    # drawing (the draw may itself emit a recycle/Burn Out
                    # event), so any resulting Chain returns to Main.
                    state["phase"], state["actor"], state["passes"] = "main", state["turn_player"], 0
                    self._draw(state, player, 1, rng)
                    self._cleanup(state, rng)
                    self._trigger_jinx_discard(state, player)
                    return
                state["decision"]["remaining"] -= 1
                if not state["decision"]["remaining"] or not row["hand"]:
                    state["decision"] = None
                    self._trigger_jinx_discard(state, player)
            elif kind == "cancel_play":
                decision = state["decision"]
                info = decision.get("cancel_play") if decision else None
                if not info or args.get("card") != info["card"]:
                    raise ValueError("no cancellable target selection")
                row["energy"] = info["energy"]
                row["power"] = list(info["power"])
                row["played"] = info["played"]
                if info.get("buff_uid") is not None:
                    spent = self._unit(state, info["buff_uid"])
                    if spent is not None:
                        spent["buff"] = info.get("buff_value", spent["buff"])
                row["hand"].insert(info["hand_index"], info["card"])
                state["chain"] = copy.deepcopy(info["chain"])
                if info.get("chain_return") is None:
                    state.pop("chain_return", None)
                else:
                    state["chain_return"] = info["chain_return"]
                if info.get("chain_from_spell") is None:
                    state.pop("chain_from_spell", None)
                else:
                    state["chain_from_spell"] = info["chain_from_spell"]
                if info.get("focus") is None:
                    state.pop("focus", None)
                else:
                    state["focus"] = info["focus"]
                state["passes"] = info["passes"]
                state["decision"] = None
                state["phase"], state["actor"] = info["phase"], info["actor"]
                return
            elif kind == "choose_card":
                decision = state["decision"]
                if decision.get("kind") != "hand_card" or args.get("card") not in decision.get("cards", []):
                    raise ValueError("invalid hand card choice")
                card = args["card"]
                code = state["cards"][card]["code"]
                if card not in row["hand"]:
                    if not decision.get("mindsplitter"):
                        raise ValueError("chosen card is no longer in hand")
                item = decision.get("item", {})
                if decision.get("mindsplitter"):
                    opponent = 1 - player
                    opponent_row = state["players"][opponent]
                    if card not in opponent_row["hand"]:
                        raise ValueError("Mindsplitter card is no longer in the revealed hand")
                    opponent_row["hand"].remove(card)
                    opponent_row["trash"].append(card)
                    opponent_row["discarded_this_turn"] = True
                    item["reveal_done"] = True
                    state["decision"] = None
                    state["chain"].append(item)
                    state["phase"], state["actor"], state["passes"] = "chain", player, 0
                    self._trigger_jinx_discard(state, opponent)
                    if state.get("optional") or state.get("chain", [])[-1] is not item:
                        return
                    self._finish_resolution(state)
                    return
                field = item.get("field")
                row["hand"].remove(card)
                row["hand"].append(card)
                state["decision"] = None
                state["phase"], state["actor"], state["passes"] = "main", player, 0
                if self.cards[code]["type"] == "unit":
                    self.apply(state, Action.make("play_unit", card=card,
                                                  location=field, accelerate=False,
                                                  payment=[], enter_target=None,
                                                  ignore_cost=True), rng)
                else:
                    self.apply(state, Action.make("play_spell", card=card, targets=[],
                                                  destination=None, spend_buff=None,
                                                  payment=[], ignore_cost=True), rng)
                return
            elif kind == "choose_target":
                decision = state["decision"]
                if args["target"] not in decision["targets"]:
                    raise ValueError("invalid target choice")
                if not self._is_targetable(state, decision.get("player", player), args["target"]):
                    raise ValueError("target is protected from enemy spells and abilities")
                if decision.get("optional_gear_effect"):
                    target_id = args["target"]
                    owner = player
                    destroyed = False
                    for row in state["players"]:
                        gear = next((gear for gear in row.get("gear", [])
                                     if gear["id"] == target_id), None)
                        if gear is not None:
                            row["gear"].remove(gear)
                            self._trash_gear_card(state, gear)
                            destroyed = True
                            break
                    if destroyed and decision.get("play_gold"):
                        self._play_gold_gear_token(state, owner, exhausted=True)
                    state["decision"] = None
                    state["optional_ordered"] = False
                    if state.get("optional"):
                        state["phase"], state["actor"] = "optional", state["optional"][0]["player"]
                        state["passes"] = 0
                    else:
                        restored = state.pop("optional_return", None)
                        if restored is None:
                            state["phase"], state["actor"], state["passes"] = "main", owner, 0
                        else:
                            if restored["phase"] == "chain" and not state.get("chain"):
                                self._finish_resolution(state)
                            else:
                                state["phase"], state["actor"], state["passes"] = (
                                    restored["phase"], restored["actor"], restored.get("passes", 0))
                    self._cleanup(state, rng)
                    return
                if decision.get("optional_return_card"):
                    target_id = args["target"]
                    row = state["players"][player]
                    if target_id not in row["trash"]:
                        raise ValueError("trash card is no longer available")
                    row["trash"].remove(target_id)
                    row["hand"].append(target_id)
                    state["decision"] = None
                    state["optional_ordered"] = False
                    if state.get("optional"):
                        state["phase"], state["actor"] = "optional", state["optional"][0]["player"]
                        state["passes"] = 0
                    else:
                        restored = state.pop("optional_return", None)
                        if restored is None:
                            state["phase"], state["actor"], state["passes"] = "main", player, 0
                        else:
                            if restored["phase"] == "chain" and not state.get("chain"):
                                self._finish_resolution(state)
                            else:
                                state["phase"], state["actor"], state["passes"] = (
                                    restored["phase"], restored["actor"], restored.get("passes", 0))
                    self._cleanup(state, rng)
                    return
                if decision.get("optional_ready_effect"):
                    target = self._unit(state, args["target"])
                    item = decision.get("item", {})
                    if target is None or target["owner"] != player or not target["exhausted"]:
                        raise ValueError("optional ready target is no longer legal")
                    self._ready_unit(state, target)
                    state["decision"] = None
                    state["optional_ordered"] = False
                    if state.get("optional"):
                        state["phase"], state["actor"], state["passes"] = (
                            "optional", state["optional"][0]["player"], 0)
                    else:
                        restored = state.pop("optional_return", None)
                        if restored is None:
                            state["phase"], state["actor"], state["passes"] = "main", player, 0
                        else:
                            state["phase"], state["actor"], state["passes"] = (
                                restored["phase"], restored["actor"], restored.get("passes", 0))
                    self._cleanup(state, rng)
                    return
                if decision.get("optional_yone_target"):
                    target = self._unit(state, args["target"])
                    item = decision.get("item", {})
                    source = self._unit(state, item.get("source"))
                    if (target is None or source is None
                            or target["owner"] == player
                            or target["location"] != f"base:{1 - player}"):
                        raise ValueError("Yone target is no longer legal")
                    self._deal_damage(state, target, self.might(state, source))
                    state["decision"] = None
                    state["optional_ordered"] = False
                    if state.get("optional"):
                        state["phase"], state["actor"], state["passes"] = (
                            "optional", state["optional"][0]["player"], 0)
                    else:
                        restored = state.pop("optional_return", None)
                        if restored is None:
                            state["phase"], state["actor"], state["passes"] = "main", player, 0
                        else:
                            state["phase"], state["actor"], state["passes"] = (
                                restored["phase"], restored["actor"], restored.get("passes", 0))
                    self._cleanup(state, rng)
                    return
                if decision.get("optional_target_effect"):
                    target = self._unit(state, args["target"])
                    if target is None or target["owner"] != player or not target["buff"]:
                        raise ValueError("optional target is no longer legal")
                    target["buff"] = 0
                    state["decision"] = None
                    state["optional_ordered"] = False
                    # Restore the saved optional/main context before drawing.
                    # Burn Out may emit Karma's recycle trigger during this
                    # draw; that trigger must return to the same context
                    # instead of capturing the transient target-decision
                    # phase.
                    if state.get("optional"):
                        state["phase"], state["actor"], state["passes"] = (
                            "optional", state["optional"][0]["player"], 0)
                    else:
                        restored = state.pop("optional_return", None)
                        if restored is None:
                            state["phase"], state["actor"], state["passes"] = "main", player, 0
                        else:
                            state["phase"], state["actor"], state["passes"] = restored["phase"], restored["actor"], restored.get("passes", 0)
                    self._draw(state, player, 1, rng)
                    self._cleanup(state, rng)
                    return
                if decision.get("optional_return_field_unit"):
                    target = self._unit(state, args["target"])
                    if (target is None or not self._is_field(state, target["location"])
                            or self.might(state, target) > 3):
                        raise ValueError("optional return target is no longer legal")
                    state["units"].remove(target)
                    self._hand_unit_card(state, target)
                    state["decision"] = None
                    state["optional_ordered"] = False
                    restored = state.pop("optional_return", None)
                    if state.get("optional"):
                        state["phase"], state["actor"], state["passes"] = (
                            "optional", state["optional"][0]["player"], 0)
                    elif restored is None:
                        state["phase"], state["actor"], state["passes"] = "main", player, 0
                    elif restored["phase"] == "chain" and not state.get("chain"):
                        self._finish_resolution(state)
                    else:
                        state["phase"], state["actor"], state["passes"] = (
                            restored["phase"], restored["actor"], restored.get("passes", 0))
                    self._cleanup(state, rng)
                    return
                if decision.get("optional_fan_target"):
                    source = self._unit(state, decision["item"].get("source"))
                    target = self._unit(state, args["target"])
                    field = decision["item"].get("field")
                    if (source is None or target is None or source["owner"] != player
                            or source["location"] != field or target["owner"] == player
                            or target["location"] != field):
                        raise ValueError("Overzealous Fan target is no longer legal")
                    state["units"].remove(source)
                    self._trash_unit_card(state, source)
                    target["location"] = f"base:{target['owner']}"
                    target["exhausted"] = True
                    target["move_count"] = target.get("move_count", 0) + 1
                    state["decision"] = None
                    state["optional_ordered"] = False
                    restored = state.pop("optional_return", None)
                    if state.get("optional"):
                        state["phase"], state["actor"], state["passes"] = (
                            "optional", state["optional"][0]["player"], 0)
                    elif restored is None:
                        state["phase"], state["actor"], state["passes"] = "main", player, 0
                    elif restored["phase"] == "chain" and not state.get("chain"):
                        self._finish_resolution(state)
                    else:
                        state["phase"], state["actor"], state["passes"] = (
                            restored["phase"], restored["actor"], restored.get("passes", 0))
                    self._cleanup(state, rng)
                    if restored is not None and restored["phase"] == "showdown" and state.get("battle") is not None:
                        self._close_showdown(state, rng)
                    return
                if decision.get("score_target"):
                    target = self._unit(state, args["target"])
                    if target is None or target["owner"] != player or target["buff"]:
                        raise ValueError("score target is no longer legal")
                    self._apply_buff(state, target)
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "main", player, 0
                    self._cleanup(state, rng)
                    if state.get("decision") is None and state.get("reveal") is None:
                        self._flush_deferred_battlefield_optionals(state)
                    return
                if decision.get("registry_ability"):
                    item = dict(decision["item"])
                    snapshot = copy.deepcopy(state)
                    state["decision"] = None
                    try:
                        self._resolve_registry_copy(state, player, item, rng, target=args["target"])
                    except Exception:
                        state.clear()
                        state.update(snapshot)
                        raise
                    if state.get("decision") is None and state.get("reveal") is None:
                        state["phase"], state["actor"], state["passes"] = "main", player, 0
                    return
                if decision.get("dragon_rage_second"):
                    item = decision["item"]
                    item["targets"] = [*item.get("targets", [])[:1], args["target"]]
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("destination_select"):
                    if decision.get("free_play"):
                        info = decision["free_play"]
                        target = self._unit(state, args["target"])
                        if target is None:
                            raise ValueError("free-play destination target is unavailable")
                        code = state["cards"][info["card"]]["code"]
                        if code == "OGN-043":
                            destinations = [f"base:{target['owner']}", *range(len(state["fields"]))]
                        elif code == "OGN-173":
                            destinations = [f"base:{target['owner']}", *range(len(state["fields"]))]
                        elif code in {"OGN-250", "OGN-270"}:
                            destinations = list(range(len(state["fields"])))
                        elif code == "OGN-258":
                            destinations = [f"base:{target['owner']}", *range(len(state["fields"]))]
                        else:
                            raise ValueError("unknown free-play destination target")
                        destinations = [destination for destination in destinations
                                        if destination != target["location"]]
                        if not destinations:
                            raise ValueError("no legal destination")
                        state["decision"] = {"kind": "choice", "player": player,
                                              "options": destinations,
                                              "free_play": info,
                                              "free_play_target": args["target"],
                                              "destination_choice": True}
                        state["phase"], state["actor"], state["passes"] = "decision", player, 0
                        return
                    item = decision["item"]
                    target = self._unit(state, args["target"])
                    if target is None:
                        raise ValueError("destination target is unavailable")
                    code = item.get("code")
                    if code == "OGN-043":
                        destinations = [f"base:{target['owner']}", *range(len(state["fields"]))]
                    elif code == "OGN-173":
                        if target["owner"] != player:
                            raise ValueError("Ride the Wind requires a friendly target")
                        destinations = [f"base:{player}", *range(len(state["fields"]))]
                    elif code in {"OGN-250", "OGN-270"}:
                        if target["owner"] != player or target["location"] != f"base:{player}":
                            raise ValueError("this spell requires a friendly unit in your base")
                        destinations = list(range(len(state["fields"])))
                    elif code == "OGN-258":
                        if target["owner"] == player:
                            raise ValueError("Dragon's Rage requires an enemy target")
                        destinations = [f"base:{target['owner']}", *range(len(state["fields"]))]
                    else:
                        raise ValueError("unknown destination target")
                    destinations = [destination for destination in destinations
                                    if destination != target["location"]]
                    if not destinations:
                        raise ValueError("no legal destination")
                    item["targets"] = [args["target"]]
                    item["dragon_rage"] = code == "OGN-258"
                    state["decision"] = {
                        "kind": "choice", "player": player,
                        "options": destinations, "item": item,
                        "destination_choice": True,
                        "dragon_rage": code == "OGN-258",
                    }
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
                    return
                if decision.get("counter_retarget"):
                    item = decision["item"]
                    # Some countered spells have an initial non-target choice
                    # followed by a target window.  Preserve that choice
                    # context when the target is selected; the generic
                    # counter retarget path must not consume it early.
                    if decision.get("whirlwind_target"):
                        item["targets"] = [args["target"]]
                        item["choice_done"] = True
                        state["decision"] = None
                        state["phase"], state["actor"], state["passes"] = (
                            "chain", item["owner"], 0)
                        return
                    item["targets"] = [args["target"]]
                    if decision.get("destination_select"):
                        target = self._unit(state, args["target"])
                        if target is None:
                            raise ValueError("Mystic Reversal target is unavailable")
                        code = item.get("code")
                        if code == "OGN-043":
                            destinations = [f"base:{target['owner']}", *range(len(state["fields"]))]
                        elif code in {"OGN-173", "OGN-250", "OGN-270"}:
                            destinations = [f"base:{item['owner']}", *range(len(state["fields"]))]
                        elif code == "OGN-258":
                            destinations = [f"base:{target['owner']}", *range(len(state["fields"]))]
                        else:
                            raise ValueError("unknown Mystic Reversal destination")
                        destinations = [destination for destination in destinations
                                        if destination != target["location"]]
                        state["decision"] = {"kind": "choice", "player": item["owner"],
                                              "options": destinations, "item": item,
                                              "destination_choice": True}
                        state["phase"], state["actor"], state["passes"] = "decision", item["owner"], 0
                        return
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("unit_ability"):
                    item = decision["item"]
                    source = self._unit(state, item["source"])
                    target = self._unit(state, args["target"])
                    if source is None or source["owner"] != player or source["exhausted"]:
                        raise ValueError("unit target ability is unavailable")
                    if item["ability"] == "caitlyn":
                        if target is None or not self._is_field(state, target["location"]):
                            raise ValueError("Caitlyn target is unavailable")
                        source["exhausted"] = True
                        self._deal_damage(state, target, self.might(state, source))
                    elif item["ability"] == "malzahar":
                        if target is not None:
                            if target["owner"] != player:
                                raise ValueError("Malzahar requires a friendly target")
                            state["units"].remove(target)
                            self._trash_unit_card(state, target)
                        else:
                            gear = next((g for g in row["gear"] if g["id"] == args["target"]), None)
                            if gear is None:
                                raise ValueError("Malzahar target is unavailable")
                            row["gear"].remove(gear)
                            self._trash_gear_card(state, gear)
                        source["exhausted"] = True
                        row["power"].extend(["spell_any", "spell_any"])
                    else:
                        raise ValueError("unknown unit target ability")
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "main", player, 0
                    self._cleanup(state, rng)
                    return
                if decision.get("legend_move_targeted"):
                    target = self._unit(state, args["target"])
                    if target is None or target["owner"] != player:
                        raise ValueError("Unforgiven requires a friendly target")
                    destinations = [f"base:{player}", *range(len(state["fields"]))]
                    destinations = [destination for destination in destinations
                                    if destination != target["location"]]
                    if not destinations:
                        raise ValueError("no legal destination")
                    state["decision"] = {
                        "kind": "choice", "player": player,
                        "options": destinations,
                        "item": {"owner": player, "target": args["target"],
                                 "legend_move": True},
                        "destination_choice": True,
                    }
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
                    return
                if decision.get("twisted_fate"):
                    item = decision["item"]
                    item["target"] = args["target"]
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("legend_action"):
                    item = decision["item"]
                    ability = item["ability"]
                    target = self._unit(state, args["target"])
                    if ability in {"buff", "ganking"}:
                        if target is None or target["owner"] != player:
                            raise ValueError("legend target must be friendly")
                        if ability == "buff":
                            if row["energy"] < 1:
                                raise ValueError("Blind Monk requires energy")
                            row["energy"] -= 1
                            self._apply_buff(state, target)
                        else:
                            target["temporary_ganking"] = True
                        row["legend_exhausted"] = True
                    elif ability == "teemo":
                        if row["energy"] < 1:
                            raise ValueError("Swift Scout requires energy")
                        target_uid = args["target"]
                        if target_uid in row["champion"] and state["cards"][target_uid]["code"] == "OGN-121":
                            row["champion"].remove(target_uid)
                            row["hand"].append(target_uid)
                        else:
                            if (target is None or target["owner"] != player
                                    or target["code"] != "OGN-121"):
                                raise ValueError("Swift Scout requires a Teemo target")
                            state["units"].remove(target)
                            self._hand_unit_card(state, target)
                        row["energy"] -= 1
                        row["legend_exhausted"] = True
                    else:
                        raise ValueError("unknown legend target ability")
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "main", player, 0
                    self._cleanup(state, rng)
                    return
                if decision.get("udyr_option"):
                    item = decision["item"]
                    target = self._unit(state, args["target"])
                    if target is None or not self._is_field(state, target["location"]):
                        raise ValueError("Udyr target is unavailable")
                    if item.get("option") == "damage":
                        self._deal_damage(state, target, 2)
                    else:
                        target["stunned"] = True
                    source = self._unit(state, item["source"])
                    if source is not None:
                        source.setdefault("udyr_choices", []).append(item["option"])
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "main", player, 0
                    self._cleanup(state, rng)
                    return
                if decision.get("king_edict"):
                    item = decision["item"]
                    item["targets"] = [args["target"]]
                    item["choice_done"] = True
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("whirlwind_target"):
                    item = decision["item"]
                    item["targets"] = [args["target"]]
                    item["choice_done"] = True
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("get_excited_target"):
                    item = decision["item"]
                    item["targets"] = [args["target"]]
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", player, 0
                    return
                if decision.get("unit_target"):
                    item = dict(decision["item"])
                    state["decision"] = None
                    state["phase"] = "main"
                    self.apply(state, Action.make("play_unit", card=item["card"],
                                                   location=item["location"],
                                                   accelerate=item["accelerate"],
                                                   payment=item["payment"],
                                                   enter_target=args["target"]), rng)
                    return
                if decision.get("free_play_unit"):
                    info = dict(decision["free_play_unit"])
                    info["enter_target"] = args["target"]
                    self._complete_free_play_unit_target(
                        state, info, args["target"], rng)
                    return
                if decision.get("multi"):
                    selected = decision.setdefault("selected", [])
                    if args["target"] in selected and not decision.get("allow_repeat"):
                        raise ValueError("target already selected")
                    if len(selected) >= decision["max"]:
                        raise ValueError("too many target choices")
                    proposed = selected + [args["target"]]
                    if (decision.get("target_pairs")
                            and not self._target_pair_extendable(decision, proposed)
                            and not self._target_pair_matches(decision, proposed)):
                        raise ValueError("Facebreaker requires one friendly and one enemy at its battlefield")
                    units = [self._unit(state, uid) for uid in proposed]
                    if decision.get("same_location"):
                        locations = {unit["location"] for unit in units if unit is not None}
                        if len(locations) > 1:
                            raise ValueError("targets must be at the same battlefield")
                    if decision.get("target_might_limit") is not None:
                        total = sum(self.might(state, unit) for unit in units if unit is not None)
                        if total > int(decision["target_might_limit"]):
                            raise ValueError("selected targets exceed the total Might limit")
                    selected.append(args["target"])
                    # The decision remains open until an explicit confirmation.
                    state["passes"] = 0
                    return
                if decision.get("trigger_target"):
                    if not state.get("chain") or state["chain"][-1] is not decision.get("item"):
                        raise ValueError("trigger target is no longer on top of the chain")
                    chain_item = state["chain"][-1]
                    chain_item["target"] = args["target"]
                    chain_item["trigger_target_pending"] = False
                    chain_item["trigger_target_finalized"] = True
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", chain_item["owner"], 0
                    return
                if decision.get("adaptatron_gear"):
                    item = dict(decision["item"])
                    item["target"] = args["target"]
                    state["decision"] = None
                    self._effect_adaptatron_conquer(state, item, rng)
                    restored = state.pop("optional_return", None)
                    state["optional_ordered"] = False
                    if restored is not None:
                        state["phase"], state["actor"], state["passes"] = restored["phase"], restored["actor"], restored.get("passes", 0)
                    else:
                        state["phase"], state["actor"] = "main", state["turn_player"]
                    self._cleanup(state, rng)
                    return
                if decision.get("gear_action"):
                    item = dict(decision["item"])
                    item["target"] = args["target"]
                    state["decision"] = None
                    self.effects.dispatch(item["effect"], state, item, rng)
                    if state.get("decision") is None and state.get("reveal") is None:
                        state["phase"], state["actor"] = "main", player
                        state["passes"] = 0
                    return
                if decision.get("play_hidden_targeted"):
                    info = decision["hidden"]
                    if args["target"] not in decision["targets"]:
                        raise ValueError("hidden card is no longer available")
                    state["decision"] = None
                    self._play_hidden_from_decision(state, player, info, [args["target"]], rng)
                    return
                if decision.get("free_play"):
                    self._complete_free_play_target(state, decision, [args["target"]], rng)
                    return
                item = dict(decision["item"])
                item["target"] = args["target"]
                if item.get("effect") == "spell":
                    item["targets"] = [args["target"]]
                resume = decision.get("resume")
                state["decision"] = None
                if resume == "combat_trigger":
                    state.setdefault("combat_trigger_selected", []).append(item)
                    self._open_combat_trigger_target(state)
                    return
                if decision.get("play_targeted"):
                    for entry in reversed(state["chain"]):
                        if entry.get("card") == item.get("card"):
                            entry["targets"] = [args["target"]]
                            self._mark_play_finalized(
                                state, entry.get("played_by", item["owner"]),
                                entry.get("card"), item=entry)
                            break
                else:
                    self.effects.dispatch(item["effect"], state, item, rng)
            elif kind == "confirm_targets":
                decision = state["decision"]
                if not decision.get("multi"):
                    raise ValueError("no multi-target decision is active")
                selected = list(decision.get("selected", []))
                if len(selected) < decision.get("min", 1):
                    raise ValueError("not enough targets selected")
                if (decision.get("target_pairs")
                        and not self._target_pair_matches(decision, selected)):
                    raise ValueError("Facebreaker requires one friendly and one enemy at its battlefield")
                units = [self._unit(state, uid) for uid in selected]
                if decision.get("same_location"):
                    locations = {unit["location"] for unit in units if unit is not None}
                    if len(locations) > 1:
                        raise ValueError("targets must be at the same battlefield")
                if decision.get("target_might_limit") is not None:
                    total = sum(self.might(state, unit) for unit in units if unit is not None)
                    if total > int(decision["target_might_limit"]):
                        raise ValueError("selected targets exceed the total Might limit")
                if decision.get("fox_fire_resolution"):
                    item = decision["item"]
                    item["targets"] = selected
                    item["fox_fire_resolution_done"] = True
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    # Continue the same resolving item without reopening
                    # priority; this selection is part of Fox-Fire's effect.
                    self._resolve_chain_item(state, rng)
                    return
                if decision.get("counter_retarget"):
                    item = decision["item"]
                    item["targets"] = selected
                    if item.get("code") == "OGN-256":
                        item["fox_fire_initial_targets"] = list(selected)
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("play_hidden_targeted"):
                    info = decision["hidden"]
                    state["decision"] = None
                    self._play_hidden_from_decision(state, player, info, selected, rng)
                    return
                if decision.get("free_play"):
                    self._complete_free_play_target(state, decision, selected, rng)
                    return
                if decision.get("resume") == "combat_trigger":
                    item = dict(decision["item"])
                    item["targets"] = selected
                    item["trigger_target_pending"] = False
                    item["trigger_target_finalized"] = True
                    state["decision"] = None
                    state.setdefault("combat_trigger_selected", []).append(item)
                    self._open_combat_trigger_target(state)
                    return
                if decision.get("trigger_target"):
                    item = state["chain"][-1]
                    item["targets"] = selected
                    item["trigger_target_pending"] = False
                    item["trigger_target_finalized"] = True
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                item = dict(decision["item"])
                item["targets"] = selected
                state["decision"] = None
                if decision.get("play_targeted"):
                    for entry in reversed(state["chain"]):
                        if entry.get("card") == item.get("card"):
                            entry["targets"] = selected
                            self._mark_play_finalized(
                                state, entry.get("played_by", item["owner"]),
                                entry.get("card"), item=entry)
                            if item.get("code") == "OGN-256":
                                entry["fox_fire_initial_targets"] = list(selected)
                            break
                else:
                    self.effects.dispatch(item["effect"], state, item, rng)
            if state["decision"] is None:
                resume = locals().get("resume")
                if resume == "close_showdown":
                    restored = state.pop("optional_return", None)
                    if restored is not None:
                        state["phase"] = restored["phase"]
                        state["actor"] = restored["actor"]
                        state["passes"] = restored.get("passes", 0)
                    else:
                        state["phase"], state["actor"] = "showdown", state.get("focus", player)
                    self._cleanup(state, rng)
                    if state.get("battle") is not None:
                        self._close_showdown(state, rng)
                else:
                    self._finish_resolution(state)
                    self._cleanup(state, rng)
        elif kind == "mulligan":
            row["hand"], row["main"] = mulligan(row["hand"], row["main"], tuple(args["slots"]), rng)
            state["mulligans"] += 1
            state["actor"] = 1-player
            if state["mulligans"] == 2:
                self._start_turn(state, rng)
        elif kind in {"exhaust_rune", "recycle_rune"}:
            rune = next(r for r in row["runes"] if r["id"] == args["rune"])
            state.setdefault("rune_undo", []).append({
                "player": player,
                "runes": copy.deepcopy(row["runes"]),
                "rune_deck": copy.deepcopy(row["rune_deck"]),
                "power": list(row["power"]),
                "energy": row["energy"],
            })
            if kind == "exhaust_rune":
                rune["exhausted"] = True
                row["energy"] += 1
            else:
                row["runes"].remove(rune)
                row["power"].extend(self.cards[rune["code"]]["domains"])
                row["rune_deck"].append({**rune, "exhausted": False})
            state["passes"] = 0
        elif kind == "undo_rune":
            history = state.get("rune_undo", [])
            if state["phase"] != "main" or not history or history[-1]["player"] != player:
                raise ValueError("rune rollback is no longer available")
            snapshot = history.pop()
            row["runes"] = copy.deepcopy(snapshot["runes"])
            row["rune_deck"] = copy.deepcopy(snapshot["rune_deck"])
            row["power"] = list(snapshot["power"])
            row["energy"] = snapshot["energy"]
            state["passes"] = 0
        elif kind == "gear_activate":
            gear = next((g for g in row["gear"] if g["id"] == args["gear"]), None)
            implementation = self._card_implementation(gear["code"]) if gear else None
            effect = args.get("effect")
            if (gear is None or gear["exhausted"]
                    or implementation is None
                    or implementation.activated_effect != effect
                    or effect not in {"gear_draw", "gear_energy_from_rainbow",
                                      "gear_rainbow_from_energy"}):
                raise ValueError("gear activation is unavailable")
            if effect == "gear_draw":
                self._pay(row, 1, args.get("payment", []))
                self.effects.dispatch(effect, state,
                                      {"effect": effect, "owner": player,
                                       "gear": gear["id"]}, rng)
            else:
                amount = int(args.get("amount", 0))
                if amount < 1:
                    raise ValueError("resource conversion amount must be positive")
                if effect == "gear_energy_from_rainbow":
                    if row["power"].count("any") < amount:
                        raise ValueError("not enough Rainbow power")
                    if self._consume_gear(state, {"owner": player, "gear": gear["id"]}) is None:
                        raise ValueError("gear activation is unavailable")
                    removed = 0
                    kept = []
                    for power in row["power"]:
                        if power == "any" and removed < amount:
                            removed += 1
                        else:
                            kept.append(power)
                    row["power"] = kept
                    row["energy"] += amount
                else:
                    if row["energy"] < amount:
                        raise ValueError("not enough Energy")
                    if self._consume_gear(state, {"owner": player, "gear": gear["id"]}) is None:
                        raise ValueError("gear activation is unavailable")
                    row["energy"] -= amount
                    row["power"].extend(["any"] * amount)
            state["passes"] = 0
        elif kind == "gear_tokens":
            gear = next((g for g in row["gear"] if g["id"] == args["gear"]), None)
            implementation = self._card_implementation(gear["code"]) if gear else None
            locations = list(args.get("locations", []))
            if (gear is None or gear["exhausted"]
                    or implementation is None
                    or implementation.activated_effect != "play_three_recruit"
                    or not locations or int(args.get("count", 0)) != 3):
                raise ValueError("token-producing gear activation is unavailable")
            state["decision"] = {
                "kind": "field_multi", "player": player,
                "fields": locations, "selected": [], "remaining": 3,
                "item": {"effect": "play_three_recruit", "owner": player,
                          "gear": gear["id"]},
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
        elif kind == "play_gear":
            card = args["card"]
            code = state["cards"][card]["code"]
            if not (code in GEAR_CODES or self._is_executable_kind(code, "gear")) or card not in row["hand"]:
                raise ValueError("unsupported gear")
            data = self.cards[code]
            ignore_energy = bool(args.get("ignore_energy"))
            self._pay(row, 0 if ignore_energy else data["energy"], args.get("payment", []))
            row["hand"].remove(card)
            triggers = []
            row["gear"].append({"id": card, "card": card, "code": code,
                                "owner": player,
                                "card_owner": self._card_owner(state, card, player),
                                "location": f"base:{player}",
                                "exhausted": code == "OGN-017",
                                "temporary": code == "SFD-104-221"})
            # Gear has no open target-selection step: it is finalized as soon
            # as payment and placement into the Base complete.
            self._mark_play_finalized(state, player, card,
                                      trigger_sink=triggers, rng=rng)
            if code == "OGN-182":
                self._draw(state, player, 1, rng)
            elif code == "OGN-212":
                self._new_unit(state, TOKEN, player, f"base:{player}", exhausted=False)
            elif code == "OGN-063":
                # Entry targeting is handled by the same Chain target window
                # as unit play triggers; no first-friendly-unit fallback.
                triggers.append({"effect": "spirit_refuge",
                                 "owner": player, "gear": card})
            implementation = self._card_implementation(code)
            if implementation and implementation.entry_trigger:
                triggers.append({"effect": implementation.entry_trigger,
                                 "owner": player, "gear": card})
            for unit in self._units(state, player):
                if unit["code"] == "OGN-091":
                    self._ready_unit(state, unit)
            if triggers:
                self._triggers(state, triggers)
                return
            state["passes"] = 0
        elif kind == "hide_card":
            card = args["card"]
            code = state["cards"][card]["code"]
            field = args["field"]
            if not self._is_hidden_code(code) or field not in range(len(state["fields"])):
                raise ValueError("invalid Hidden card or battlefield")
            capacity = 2 if state["fields"][field]["code"] == "OGN-278" else 1
            if state["fields"][field]["controller"] != player or sum(
                    h["field"] == field for owner in state["players"] for h in owner.get("hidden", [])) >= capacity:
                raise ValueError("Hidden card requires an empty battlefield you control")
            if args.get("use_energy"):
                if row["legend"] != "OGN-263" or row["energy"] < 1:
                    raise ValueError("Swift Scout energy hide is unavailable")
                row["energy"] -= 1
            elif args.get("ignore_cost"):
                if not row.get("free_hide_turn"):
                    raise ValueError("free Hidden placement is unavailable")
            else:
                self._pay(row, 0, args["payment"])
            if card in row["hand"]:
                row["hand"].remove(card)
            elif card in row["champion"]:
                row["champion"].remove(card)
            else:
                raise ValueError("Hidden card is not in hand or Champion Zone")
            row["hidden"].append({"id": card, "card": card, "code": code, "owner": player,
                                  "field": field, "turn": state["turn"]})
            state["passes"] = 0
        elif kind == "play_hidden":
            hidden = next((h for h in row["hidden"] if h["id"] == args["card"]), None)
            if hidden is None or hidden["turn"] >= state["turn"]:
                raise ValueError("Hidden card is not ready")
            row["hidden"].remove(hidden)
            row["hand"].append(hidden["card"])
            code = hidden["code"]
            kind2 = ("play_unit" if self.cards[code]["type"] == "unit"
                     else "play_gear" if self.cards[code]["type"] == "gear"
                     else "play_spell")
            if kind2 == "play_unit":
                nested = Action.make(kind2, card=hidden["card"], location=hidden["field"],
                                     accelerate=False, payment=[], enter_target=None,
                                     ignore_cost=True, hidden_field=hidden["field"])
            elif kind2 == "play_gear":
                nested = Action.make(kind2, card=hidden["card"], payment=[], ignore_energy=True)
            else:
                nested = Action.make(kind2, card=hidden["card"], targets=args.get("targets", []),
                                     destination=None, spend_buff=None, payment=[], ignore_cost=True,
                                     hidden_field=hidden["field"])
            self.apply(state, nested, rng)
        elif kind == "play_hidden_targeted":
            hidden = next((h for h in row["hidden"] if h["id"] == args["card"]), None)
            if hidden is None or hidden["turn"] >= state["turn"]:
                raise ValueError("Hidden card is not ready")
            state["decision"] = {"kind": "target", "player": player,
                                  "targets": list(args["target_candidates"]),
                                  "multi": bool(args.get("multi")) or args.get("target_max", 1) > 1,
                                  "min": args.get("target_min", 1),
                                  "max": args.get("target_max", 1), "selected": [],
                                  "allow_repeat": bool(args.get("allow_repeat", False)),
                                  "target_pairs": [list(pair) for pair in args.get("target_pairs", [])],
                                  "target_might_limit": args.get("target_might_limit"),
                                  "same_location": bool(args.get("same_location", False)),
                                  "item": {"effect": "hidden_play", "owner": player},
                                  "play_hidden_targeted": True,
                                  "hidden": {"card": hidden["id"], "field": hidden["field"],
                                             "code": hidden["code"]}}
            state["phase"], state["actor"] = "decision", player
        elif kind == "gear_resource":
            gear = next((g for g in row["gear"] if g["id"] == args["gear"]), None)
            if gear is None or gear["exhausted"]:
                raise ValueError("gear resource is unavailable")
            if self._consume_gear(state, {"owner": player, "gear": args["gear"]}) is None:
                raise ValueError("gear resource is unavailable")
            if args.get("energy"):
                row["energy"] += int(args["energy"])
            else:
                row["power"].append(args["domain"])
            state["passes"] = 0
        elif kind == "gear_targeted":
            gear = next((g for g in row["gear"] if g["id"] == args["gear"]), None)
            if (gear is None or gear["exhausted"]
                    or args.get("effect") not in {"gear_debuff", "gear_buff_exhausted", "gear_move",
                                                   "gear_armory_protect", "gear_baited_hook",
                                                   "gear_damage", "gear_return", "gear_buff_three"}):
                raise ValueError("gear target ability is unavailable")
            state["decision"] = {
                "kind": "target", "player": player,
                "targets": list(args.get("target_candidates", [])),
                "item": {"effect": args["effect"], "owner": player, "gear": args["gear"]},
                "gear_action": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
        elif kind == "gear_target":
            gear = next((g for g in row["gear"] if g["id"] == args["gear"]), None)
            if gear is None or gear["exhausted"]:
                raise ValueError("gear ability is unavailable")
            self.effects.dispatch(args["effect"], state,
                                  {"effect": args["effect"], "owner": player,
                                   "gear": args["gear"], "target": args["target"]}, rng)
            state["passes"] = 0
        elif kind == "gear_ready_next":
            if self._consume_gear(state, {"owner": player, "gear": args["gear"]}) is None:
                raise ValueError("gear ability is unavailable")
            row["ready_play"] = True
            state["passes"] = 0
        elif kind == "gear_tome":
            if self._consume_gear(state, {"owner": player, "gear": args["gear"]}) is None:
                raise ValueError("gear ability is unavailable")
            row["spell_bonus_damage"] = row.get("spell_bonus_damage", 0) + 1
            state["passes"] = 0
        elif kind == "gear_kill":
            gear = next((g for g in row["gear"] if g["id"] == args["gear"]), None)
            if gear is None:
                raise ValueError("gear is unavailable")
            row["gear"].remove(gear)
            self._trash_gear_card(state, gear)
            self._gear_ability_used(state, player)
            self._draw(state, player, 1, rng)
            self._channel_rune(state, player, exhausted=True)
            state["passes"] = 0
        elif kind == "gear_grab":
            if self._consume_gear(state, {"owner": player, "gear": args["gear"]}) is None:
                raise ValueError("gear ability is unavailable")
            if row["energy"] < 1 or len(row["trash"]) < 3:
                raise ValueError("Garbage Grabber cost is unavailable")
            row["energy"] -= 1
            self._recycle_cards_to_main(state, player, list(row["trash"][:3]),
                                        source="trash", rng=rng)
            self._draw(state, player, 1, rng)
            state["passes"] = 0
        elif kind == "gear_forge_recycle":
            gear = next((g for g in row["gear"] if g["id"] == args["gear"]), None)
            if gear is None or gear["code"] != "OGN-212" or gear["exhausted"]:
                raise ValueError("Forge of the Future is unavailable")
            row["gear"].remove(gear)
            self._trash_gear_card(state, gear)
            self._gear_ability_used(state, player)
            cards = [uid for owner in state["players"] for uid in owner["trash"]]
            self._open_reveal(state, owner=player, cards=cards, mode="select",
                              chooser=player, minimum=0, maximum=min(4, len(cards)),
                              effect="forge_recycle", choices=cards, rng=rng)
            return
        elif kind == "optional_effect":
            optional = state.get("optional", [])
            item = next((entry for entry in optional if entry["id"] == args["optional"]), None)
            if item is None or item["player"] != player or (optional and optional[0]["id"] != item["id"]):
                raise ValueError("optional effect is unavailable")
            optional.remove(item)
            if args.get("accept"):
                self._resolve_optional(state, item, rng)
            state["passes"] = 0
            if state.get("decision") is not None or state.get("reveal") is not None:
                # The optional effect opened a target/reveal window. Its saved return
                # context is restored by the target confirmation handler.
                return
            if optional:
                state["actor"] = optional[0]["player"]
            else:
                restored = state.pop("optional_return", None)
                state["optional_ordered"] = False
                if restored is not None:
                    if restored["phase"] == "chain" and not state["chain"]:
                        # The optional trigger was created while the chain
                        # item was resolving.  Resume normal chain cleanup so
                        # an empty chain returns to the saved main/showdown
                        # phase instead of leaving a dead chain window open.
                        self._finish_resolution(state)
                    else:
                        state["phase"] = restored["phase"]
                        state["actor"] = restored["actor"]
                        state["passes"] = restored.get("passes", 0)
                self._cleanup(state, rng)
                if item.get("resume") == "close_showdown" and state.get("battle") is not None:
                    self._close_showdown(state, rng)
        elif kind == "order_optional":
            optional = state.get("optional", [])
            order = args.get("order", [])
            ids = [item["id"] for item in optional]
            if (not optional or any(item["player"] != player for item in optional)
                    or set(order) != set(ids) or len(order) != len(ids)):
                raise ValueError("optional trigger order is unavailable")
            state["optional"] = [next(item for item in optional if item["id"] == uid)
                                  for uid in order]
            state["optional_ordered"] = True
            state["passes"] = 0
        elif kind == "legend_energy":
            if (row["legend"] != "OGN-253" or row["legend_exhausted"]
                    or not self._played_for_legion(state, player)):
                raise ValueError("Hand of Noxus Legion ability is unavailable")
            row["legend_exhausted"] = True
            row["energy"] += 1
            state["passes"] = 0
        elif kind == "legend_spell_power":
            row["legend_exhausted"] = True
            row["power"].append("spell_any")
            state["passes"] = 0
        elif kind == "legend_rainbow":
            implementation = self._card_implementation(row["legend"])
            if (implementation is None
                    or implementation.activated_effect != "legend_rainbow"
                    or not implementation.reaction
                    or row["legend_exhausted"]):
                raise ValueError("Legend Rainbow ability is unavailable")
            row["legend_exhausted"] = True
            row["power"].append("any")
            state["passes"] = 0
        elif kind == "unit_registry_ability":
            source = self._unit(state, args["unit"])
            implementation = self._card_implementation(source["code"]) if source else None
            if (source is None or source["owner"] != player or source["exhausted"]
                    or source.get("buff", 0) <= 0 or implementation is None
                    or implementation.activated_effect != args.get("effect")):
                raise ValueError("registered unit ability is unavailable")
            source["buff"] -= 1
            source["exhausted"] = True
            source["temporary"] += 4
            state["passes"] = 0
        elif kind == "unit_udyr":
            source = self._unit(state, args["unit"])
            if (source is None or source["owner"] != player or source["code"] not in {"OGN-157", "OGN-111"}
                    or source["exhausted"] or not source["buff"]):
                raise ValueError("Udyr ability is unavailable")
            source["buff"] -= 1
            state["decision"] = {"kind": "choice", "player": player,
                                  "options": list(args.get("options", [])),
                                  "item": {"effect": "udyr_choice", "owner": player,
                                            "source": source["id"]}, "udyr_choice": True}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
        elif kind == "unit_ability_targeted":
            source = self._unit(state, args["unit"])
            ability = args.get("ability")
            if source is None or source["owner"] != player or source["exhausted"]:
                raise ValueError("unit target ability is unavailable")
            if ability == "caitlyn":
                valid = (source["code"] in {"OGN-068", "OGN-111"} and self._is_field(state, source["location"])
                         and any(self._is_field(state, u["location"]) for u in state["units"]))
            elif ability == "malzahar":
                valid = source["code"] in {"OGN-113", "OGN-111"}
            else:
                valid = False
            if not valid:
                raise ValueError("unit target ability is unavailable")
            state["decision"] = {
                "kind": "target", "player": player,
                "targets": list(args.get("target_candidates", [])),
                "item": {"source": source["id"], "owner": player, "ability": ability},
                "unit_ability": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
        elif kind == "unit_malzahar":
            source = self._unit(state, args["unit"])
            if source is None or source["owner"] != player or source["code"] not in {"OGN-113", "OGN-111"} or source["exhausted"]:
                raise ValueError("Malzahar ability is unavailable")
            target = self._unit(state, args["target"])
            if target is not None:
                if target["owner"] != player:
                    raise ValueError("Malzahar requires a friendly target")
                state["units"].remove(target)
                self._trash_unit_card(state, target)
            else:
                gear = next((g for g in row["gear"] if g["id"] == args["target"]), None)
                if gear is None:
                    raise ValueError("Malzahar target is unavailable")
                row["gear"].remove(gear)
                self._trash_gear_card(state, gear)
            source["exhausted"] = True
            row["power"].extend(["spell_any", "spell_any"])
            state["passes"] = 0
        elif kind == "unit_caitlyn":
            unit = self._unit(state, args["unit"])
            target = self._unit(state, args["target"])
            if (unit is None or unit["owner"] != player or unit["code"] not in {"OGN-068", "OGN-111"}
                    or unit["exhausted"] or not self._is_field(state, unit["location"])
                    or target is None or not self._is_field(state, target["location"])
                    or state["phase"] not in {"main", "showdown"}):
                raise ValueError("Caitlyn ability is unavailable")
            unit["exhausted"] = True
            self._deal_damage(state, target, self.might(state, unit))
            self._cleanup(state, rng)
            state["passes"] = 0
        elif kind == "unit_buff":
            unit = self._unit(state, args["unit"])
            if unit is None or unit["owner"] != player or unit["code"] not in {"OGN-078", "OGN-111"} or unit["exhausted"]:
                raise ValueError("Lee Sin ability is unavailable")
            unit["exhausted"] = True
            unit["buff"] = unit["buff"] + 1
            state["passes"] = 0
        elif kind == "unit_recycle_buff":
            unit = self._unit(state, args["unit"])
            if unit is None or unit["owner"] != player or unit["code"] not in {"OGN-036", "OGN-111"} or unit["exhausted"]:
                raise ValueError("Vi ability is unavailable")
            if not row["trash"]:
                raise ValueError("Vi requires a card in trash")
            self._recycle_cards_to_main(state, player, [row["trash"][0]],
                                        source="trash", rng=rng)
            unit["exhausted"] = True
            unit["temporary"] += 1
            state["passes"] = 0
        elif kind == "legend_recruit":
            if row["legend"] != "OGN-265" or row["legend_exhausted"] or row["energy"] < 1:
                raise ValueError("Herald of the Arcane ability is unavailable")
            row["energy"] -= 1
            row["legend_exhausted"] = True
            self._new_unit(state, TOKEN, player, f"base:{player}")
            state["passes"] = 0
        elif kind == "legend_channel":
            if (row["legend"] != "OGN-249" or row["legend_exhausted"]
                    or not row["rune_deck"]
                    or not any(option["owner"] == player for option in state.get("legend_options", []))):
                raise ValueError("Relentless Storm ability is unavailable")
            row["legend_exhausted"] = True
            rune = {**row["rune_deck"].pop(0), "exhausted": True}
            row["runes"].append(rune)
            state["legend_options"] = [option for option in state.get("legend_options", [])
                                        if option["owner"] != player]
            state["passes"] = 0
        elif kind == "legend_targeted":
            ability = args.get("ability")
            allowed = {"buff": "OGN-257", "ganking": "OGN-267", "teemo": "OGN-263"}
            if row["legend"] != allowed.get(ability) or row["legend_exhausted"]:
                raise ValueError("legend target ability is unavailable")
            if ability == "buff" and row["energy"] < 1:
                raise ValueError("Blind Monk requires energy")
            if ability == "teemo" and row["energy"] < 1:
                raise ValueError("Swift Scout requires energy")
            state["decision"] = {
                "kind": "target", "player": player,
                "targets": list(args.get("target_candidates", [])),
                "item": {"owner": player, "ability": ability},
                "legend_action": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
        elif kind == "legend_move_targeted":
            if row["legend"] != "OGN-259" or row["legend_exhausted"] or row["energy"] < 2:
                raise ValueError("Unforgiven ability is unavailable")
            state["decision"] = {
                "kind": "target", "player": player,
                "targets": list(args.get("target_candidates", [])),
                "item": {"owner": player, "ability": "legend_move"},
                "legend_move_targeted": True,
            }
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
        elif kind == "legend_buff":
            if row["legend"] != "OGN-257" or row["legend_exhausted"] or row["energy"] < 1:
                raise ValueError("Blind Monk ability is unavailable")
            target = self._unit(state, args["target"])
            if target is None or target["owner"] != player:
                raise ValueError("invalid Blind Monk target")
            row["energy"] -= 1
            row["legend_exhausted"] = True
            self._apply_buff(state, target)
            state["passes"] = 0
        elif kind == "legend_ganking":
            if row["legend"] != "OGN-267" or row["legend_exhausted"]:
                raise ValueError("Bounty Hunter ability is unavailable")
            target = self._unit(state, args["target"])
            if target is None or target["owner"] != player:
                raise ValueError("invalid Bounty Hunter target")
            row["legend_exhausted"] = True
            target["temporary_ganking"] = True
            state["passes"] = 0
        elif kind == "legend_teemo":
            if row["legend"] != "OGN-263" or row["legend_exhausted"] or row["energy"] < 1:
                raise ValueError("Swift Scout ability is unavailable")
            target = args["target"]
            row["energy"] -= 1
            row["legend_exhausted"] = True
            if target in row["champion"] and state["cards"][target]["code"] == "OGN-121":
                row["champion"].remove(target)
                row["hand"].append(target)
            else:
                unit = self._unit(state, target)
                if unit is None or unit["owner"] != player or unit["code"] != "OGN-121":
                    raise ValueError("Swift Scout requires a Teemo unit")
                state["units"].remove(unit)
                self._hand_unit_card(state, unit)
            state["passes"] = 0
        elif kind == "legend_move":
            if row["legend"] != "OGN-259" or row["legend_exhausted"] or row["energy"] < 2:
                raise ValueError("Unforgiven ability is unavailable")
            target = self._unit(state, args["target"])
            destination = args["destination"]
            if target is None or target["owner"] != player or destination == target["location"]:
                raise ValueError("invalid Unforgiven target")
            if destination != f"base:{player}" and not self._is_field(state, destination):
                raise ValueError("invalid Unforgiven destination")
            row["energy"] -= 2
            row["legend_exhausted"] = True
            self._resolve_move(state, [target], destination, player, rng, from_effect=True)
            state["passes"] = 0
        elif kind == "play_counter":
            card = args["card"]
            code = state["cards"][card]["code"]
            implementation = self._card_implementation(code)
            if ((code not in {"OGN-045", "OGN-064", "OGN-080"}
                 and not (implementation and implementation.counter_scope))
                    or card not in row["hand"]):
                raise ValueError("counter spell is unavailable")
            data = self.cards[code]
            self._pay(row, data["energy"], args.get("payment", []))
            row["hand"].remove(card)
            item = {"effect": "counter", "owner": player, "card": card,
                    "code": code, "targets": [], "counter_targets": list(args.get("targets", []))}
            self._enter_chain(state, [item])
            state["decision"] = {"kind": "chain_target", "player": player,
                                  "targets": list(args.get("targets", [])), "item": item}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
        elif kind == "play_field_targeted":
            card = args["card"]
            code = state["cards"][card]["code"]
            if code not in (FIELD_TARGET_SPELLS | {"OGN-268"}) or card not in row["hand"]:
                raise ValueError("field-target spell is unavailable")
            data = self.cards[code]
            energy = max(0, data["energy"] - row.get("spell_discount", 0))
            self._pay(row, energy, args.get("payment", []))
            row["spell_discount"] = 0
            row["hand"].remove(card)
            finalized_before = self._played_for_legion(state, player)
            item = {"effect": "spell", "owner": player, "card": card,
                    "code": code, "targets": [], "field": None,
                    "legion": bool(finalized_before),
                    "x": 0,
                    "post_triggers": self._spell_post_triggers(state, player, finalized_before)}
            self._enter_chain(state, [item])
            state["decision"] = {"kind": "field", "player": player,
                                  "fields": list(args.get("fields", [])), "item": item,
                                  "x_choice": bool(args.get("x_choice", False)),
                                  "x_max": len(row["power"]) if args.get("x_choice") else 0}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
        elif kind == "play_spell_targeted":
            card = args["card"]
            code = state["cards"][card]["code"]
            implementation = self._card_implementation(code)
            registry_targeted = bool(implementation and implementation.target_scope)
            if ((code not in (SIMPLE_TARGET_SPELLS | PAIR_TARGET_SPELLS | DESTINATION_TARGET_SPELLS | OPTIONAL_TARGET_SPELLS | CONSTRAINED_MULTI_TARGET_SPELLS | SEQUENTIAL_TARGET_SPELLS | {"OGN-029", "OGN-104", "OGN-105", "OGN-183", "OGN-206", "OGN-248"})
                 and not registry_targeted) or card not in row["hand"]):
                raise ValueError("target-selection spell is unavailable")
            data = self.cards[code]
            payment = args.get("payment", [])
            spend = args.get("spend_buff")
            finalized_before = self._played_for_legion(state, player)
            before = {
                "card": card, "energy": row["energy"], "power": list(row["power"]),
                "played": row["played"], "hand_index": row["hand"].index(card),
                "buff_uid": spend, "buff_value": self._unit(state, spend)["buff"] if spend else None,
                "phase": state["phase"], "actor": state["actor"],
                "chain": copy.deepcopy(state["chain"]),
                "chain_return": state.get("chain_return"),
                "chain_from_spell": state.get("chain_from_spell"),
                "focus": state.get("focus"), "passes": state.get("passes", 0),
            }
            spell_energy = 0 if spend is not None else max(0, data["energy"] - row.get("spell_discount", 0))
            self._pay(row, spell_energy, payment)
            if spend is None:
                row["spell_discount"] = 0
            if spend is not None:
                spent = self._unit(state, spend)
                if spent is None or spent["owner"] != player or not spent["buff"]:
                    raise ValueError("invalid buff payment")
                spent["buff"] = 0
            row["hand"].remove(card)
            item = {"effect": "spell", "owner": player, "card": card,
                    "code": code, "targets": [], "destination": args.get("destination"),
                    "legion": bool(finalized_before)}
            if code == "OGN-183":
                item["deck_options"] = list(args.get("deck_options", []))
            # Ravenbloom/Darius/Viktor are generated only after this spell
            # resolves; the shared helper keeps all spell entry paths aligned.
            item["post_triggers"] = self._spell_post_triggers(
                state, player, finalized_before)
            # Keep a pending spell item while the player chooses its target;
            # target confirmation fills that item before normal chain resolution.
            self._enter_chain(state, [item])
            if code == "OGN-008":
                # Get Excited! has a mandatory discard before its damage
                # target exists.  Keep the card on the Chain, open the
                # discard window first, then reuse the normal target-click
                # decision opened by the discard handler.
                state["decision"] = {"kind": "discard", "player": player,
                                      "remaining": 1, "item": item,
                                      "get_excited_discard": True}
                state["phase"], state["actor"], state["passes"] = "decision", player, 0
                return
            state["decision"] = {"kind": "target", "player": player,
                                  "targets": list(args.get("target_candidates", [])),
                                  "multi": (code in (PAIR_TARGET_SPELLS | OPTIONAL_TARGET_SPELLS | CONSTRAINED_MULTI_TARGET_SPELLS | {"OGN-029", "OGN-105", "OGN-206", "OGN-248"})
                                            or (registry_targeted and int(args.get("target_max", 1)) > 1)), "min": int(args.get("target_min", 1)),
                                  "max": int(args.get("target_max", 1)), "selected": [],
                                  "allow_repeat": bool(args.get("allow_repeat", False)),
                                  "target_pairs": [list(pair) for pair in (args.get("target_pairs") or [])
                                                   if pair is not None],
                                  "ordered_pairs": bool(args.get("ordered_pairs", False)),
                                  "destination_select": bool(args.get("destination_select", False)),
                                  "target_might_limit": args.get("target_might_limit"),
                                  "same_location": bool(args.get("same_location", False)),
                                  "item": item, "play_targeted": True,
                                  "registry_targeted": registry_targeted,
                                  "cancel_play": before if code in {"OGN-104", "OGN-183"} else None}
            state["phase"], state["actor"] = "decision", player
            state["passes"] = 0
        elif kind == "play_unit_targeted":
            card = args["card"]
            if card not in row["hand"] or state["cards"][card]["code"] != "OGN-016":
                raise ValueError("target-selection unit is unavailable")
            state["decision"] = {
                "kind": "unit_target", "player": player,
                "targets": list(args.get("target_candidates", [])),
                "item": args, "unit_target": True,
            }
            state["phase"], state["actor"] = "decision", player
            state["passes"] = 0
        elif kind in {"play_unit", "play_spell"}:
            card = args["card"]
            code = state["cards"][card]["code"]
            data = self.cards[code]
            implementation = self._card_implementation(code)
            finalized_before = self._played_for_legion(state, player)
            was_legion = finalized_before > 0
            if kind == "play_unit":
                ignore_cost = bool(args.get("ignore_cost"))
                additional_cost = bool(args.get("additional_cost"))
                sacrifice_id = args.get("sacrifice")
                discard_card = args.get("discard_card")
                additional_gear_id = args.get("additional_gear")
                spend_buffs = list(args.get("spend_buffs") or [])
                kill_units = list(args.get("kill_units") or [])
                ignore_energy = bool(args.get("ignore_energy"))
                energy_reduction = max(0, int(args.get("energy_reduction", 0)))
                additional_energy = (implementation.additional_cost_energy
                                     if implementation is not None else
                                     (1 if code == "OGN-044" else 0))
                energy = 0 if (ignore_cost or ignore_energy) else max(0, data["energy"] - energy_reduction - (2 if code == "OGN-012" and was_legion else 0)
                                                    - (2 if discard_card else 0)
                                                    + (additional_energy if additional_cost else 0))
                additional_power = (implementation.additional_cost_power
                                    if implementation is not None else 0)
                power_cost = max(0, data["power_cost"] - len(spend_buffs) - len(kill_units))
                power_cost += additional_power if additional_cost else 0
                self._pay(row, energy, [] if ignore_cost else args["payment"])
                if not ignore_cost and discard_card is not None:
                    if discard_card not in row["hand"] or discard_card == card:
                        raise ValueError("Brazen Buccaneer requires a different card to discard")
                    row["hand"].remove(discard_card)
                    row["trash"].append(discard_card)
                    row["discarded_this_turn"] = True
                if (not ignore_cost and implementation is not None
                        and implementation.additional_cost_effect == "return_gear"):
                    gear = next((gear for gear in row.get("gear", [])
                                 if gear["id"] == additional_gear_id), None)
                    if gear is None:
                        raise ValueError("Legion Quartermaster requires a friendly Gear to return")
                    row["gear"].remove(gear)
                    self._hand_gear_card(state, gear)
                for uid in spend_buffs:
                    spent = self._unit(state, uid)
                    if spent is None or spent["owner"] != player or spent["buff"] <= 0:
                        raise ValueError("Kraken Hunter requires available buffs")
                    spent["buff"] -= 1
                for uid in kill_units:
                    killed = self._unit(state, uid)
                    if killed is None or killed["owner"] != player:
                        raise ValueError("Commander Ledros requires friendly units")
                    state["units"].remove(killed)
                    self._trash_unit_card(state, killed)
                if not ignore_cost and code == "OGN-208":
                    sacrificed = self._unit(state, sacrifice_id)
                    if sacrificed is None or sacrificed["owner"] != player:
                        raise ValueError("Cruel Patron requires a friendly unit sacrifice")
                    state["units"].remove(sacrificed)
                    self._trash_unit_card(state, sacrificed)
                zone = row["hand"] if card in row["hand"] else row["champion"]
                zone.remove(card)
                ready = (any(u["code"] == "OGN-011" for u in self._units(state, player))
                         or row.get("ready_play", False))
                ready = ready or code == "OGN-159"
                ready = ready or self._entry_ready(state, code, player)
                if code == "OGN-035":
                    ready = ready or any(field["controller"] == 1-player for field in state["fields"])
                if code == "OGN-079":
                    ready = ready or state["victory"] - state["points"][1-player] <= 3
                unit = self._new_unit(state, code, player, args["location"], card=card, exhausted=not ready)
                if args.get("hidden_field") is not None:
                    unit["hidden_field"] = args["hidden_field"]
                # Rally the Troops creates a turn-scoped replacement trigger
                # for every later friendly unit play.  Apply it at the common
                # unit-entry point so hand, Hidden, and nested free plays all
                # share the same behavior.
                if any(entry.get("owner") == player and entry.get("turn") == state["turn"]
                       for entry in state.get("rally_effects", [])):
                    self._apply_buff(state, unit)
                if (additional_cost and implementation is not None
                        and implementation.additional_cost_effect == "buff_self"):
                    self._apply_buff(state, unit)
                if (row["legend"] == "OGN-249" and not row["legend_exhausted"]
                        and self.might(state, unit) >= 5):
                    state.setdefault("legend_options", []).append({"owner": player,
                                                                      "source": unit["id"]})
                triggers = self._second_card_triggers(state, player)
                implementation = self._card_implementation(code)
                if (additional_cost and implementation is not None
                        and implementation.additional_cost_effect == "blast_corps"):
                    triggers.append({"effect": "blast_corps", "source": unit["id"],
                                     "owner": player})
                if (additional_cost and implementation is not None
                        and implementation.additional_cost_effect == "frostcoat_debuff"):
                    triggers.append({"effect": "frostcoat_debuff", "source": unit["id"],
                                     "owner": player})
                if implementation and implementation.entry_trigger:
                    trigger = {"effect": implementation.entry_trigger,
                               "source": unit["id"], "owner": player}
                    if implementation.entry_trigger == "return_friendly_enemy":
                        friendly = [candidate["id"] for candidate in self._units(state, player)
                                    if candidate["id"] != unit["id"]]
                        enemy = [candidate["id"] for candidate in self._units(state, 1 - player)]
                        trigger.update({
                            "target_multi": True,
                            "target_min": 2,
                            "target_max": 2,
                            "target_pairs": [[friendly_id, enemy_id]
                                             for friendly_id in friendly
                                             for enemy_id in enemy],
                        })
                    triggers.append(trigger)
                if code == "OGN-067":
                    triggers.append({"effect": "blitz_move", "source": unit["id"], "owner": player})
                if code == "OGN-016" and was_legion:
                    triggers.append({"effect": "buff_two", "source": unit["id"], "owner": player,
                                     "target": args.get("enter_target")})
                if code == "OGN-217" and was_legion:
                    triggers.append({"effect": "buff_self", "source": unit["id"], "owner": player})
                if code == "OGN-003":
                    triggers.append({"effect": "discard_one", "source": unit["id"], "owner": player})
                if code == "OGN-234":
                    triggers.append({"effect": "kill_target", "source": unit["id"], "owner": player})
                if code == "OGN-061":
                    triggers.append({"effect": "poro_herder", "source": unit["id"], "owner": player})
                if code == "OGN-092":
                    triggers.append({"effect": "riptide_damage", "source": unit["id"], "owner": player})
                if code == "OGN-038":
                    triggers.append({"effect": "kadregrin_draw", "source": unit["id"], "owner": player})
                if code == "OGN-149":
                    triggers.append({"effect": "snapvine_fight", "source": unit["id"], "owner": player})
                if code == "OGN-097":
                    trigger = {"effect": "fae_debuff", "source": unit["id"], "owner": player}
                    if unit.get("hidden_field") is not None:
                        trigger["hidden_field"] = unit["hidden_field"]
                    triggers.append(trigger)
                if code == "OGN-100":
                    triggers.append({"effect": "vision", "source": unit["id"], "owner": player})
                if code == "OGN-106":
                    triggers.append({"effect": "sprite_mother", "source": unit["id"], "owner": player})
                if code == "OGN-116":
                    triggers.append({"effect": "watcher_debuff", "source": unit["id"], "owner": player})
                if code == "OGN-188":
                    triggers.append({"effect": "return_field_unit", "source": unit["id"], "owner": player})
                if code == "OGN-191":
                    triggers.append({"effect": "move_field_unit", "source": unit["id"], "owner": player})
                if code == "OGN-197":
                    triggers.append({"effect": "buff_self_three", "source": unit["id"], "owner": player})
                if code == "OGN-026":
                    state["players"][1 - player]["cards_locked_turn"] = True
                if code == "OGN-031":
                    row["spell_discount"] = 5
                if code == "OGN-044" and additional_cost:
                    triggers.append({"effect": "draw_one", "source": unit["id"], "owner": player})
                if code == "OGN-147":
                    if any(other["id"] != unit["id"] and other["buff"]
                           for other in self._units(state, player)):
                        triggers.append({"effect": "wildclaw_optional",
                                         "source": unit["id"], "owner": player})
                if code == "OGN-141":
                    triggers.append({"effect": "kinkou_buff", "source": unit["id"],
                                     "owner": player, "target_multi": True})
                if code == "OGN-230":
                    triggers.append({"effect": "albus_optional", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-167" and args.get("hidden_field") is not None:
                    triggers.extend({"effect": "ember_hidden_buff", "source": source["id"], "owner": player}
                                    for source in self._units(state, player) if source["code"] == "OGN-167")
                if code == "OGN-199":
                    # The target is chosen when the triggered ability is put
                    # on the Chain.  Store the original location for the
                    # errata-defined swap and allow a target at any other
                    # location (RUP5 811.1.d.3).
                    triggers.append({"effect": "tideturner_target", "source": unit["id"],
                                     "owner": player, "original_location": args["location"]})
                if state["turn_player"] != player:
                    triggers.extend({"effect": "viktor_innovator", "source": source["id"], "owner": player}
                                    for source in self._units(state, player)
                                    if source["code"] == "OGN-117")
                if code == "OGN-051":
                    triggers.append({"effect": "stun_target", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-192":
                    triggers.append({"effect": "mindsplitter", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-082":
                    triggers.append({"effect": "buff_eight", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-132":
                    triggers.append({"effect": "ready_target", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-136":
                    triggers.append({"effect": "buff_target", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-087":
                    triggers.append({"effect": "draw_one", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-137":
                    triggers.append({"effect": "channel_one", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-164":
                    triggers.append({"effect": "buff_self", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-165":
                    triggers.append({"effect": "return_unit_trigger", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-218" and was_legion:
                    triggers.extend({"effect": "drummer", "owner": player,
                                     "location": args["location"]} for _ in range(2))
                if code == "OGN-225":
                    triggers.append({"effect": "solari_target", "source": unit["id"],
                                     "owner": player})
                if code == "OGN-243" and was_legion:
                    triggers.append({"effect": "ready_self", "source": unit["id"],
                                     "owner": player})
                for other in self._units(state, player):
                    if other["id"] != unit["id"] and other["code"] == "OGN-139":
                        triggers.append({"effect": "buff_self", "source": other["id"],
                                         "owner": player})
                if code == "OGN-211":
                    triggers.append({"effect": "drummer", "owner": player, "location": args["location"]})
                if code == "OGN-223":
                    triggers.append({"effect": "peak", "source": unit["id"], "owner": player})
                if (code in {"OGN-030", "OGN-086", "OGN-100", "OGN-171", "OGN-174"}
                        or (implementation is not None
                            and implementation.global_effect == "vision_recycle")):
                    triggers.append({"effect": "discard_two" if code == "OGN-030" else "vision",
                                     "source": unit["id"], "owner": player})
                elif any(
                        other["code"] == "OGN-100"
                        or (
                            self._card_implementation(other["code"]) is not None
                            and self._card_implementation(other["code"]).global_effect in {"mechs_vision", "vision_recycle"}
                            and "Mech" in self.cards.get(code, {}).get("tags", [])
                        )
                        for other in self._units(state, player)):
                    triggers.append({"effect": "vision", "source": unit["id"], "owner": player})
                if self._is_accelerate_code(code):
                    # Keep the unit visible in its destination while the
                    # controller completes the Accelerate payment.  This is a
                    # play-time decision (RUP5 805.2), so no later trigger or
                    # showdown is allowed to advance until it is resolved.
                    state["decision"] = {
                        "kind": "choice", "player": player,
                        "options": ["accelerate", "skip"],
                        "accelerate": {
                            "unit": unit["id"], "player": player,
                            "code": code, "location": args["location"],
                            "finalized_before": finalized_before,
                            "domains": list(data["domains"]),
                            "triggers": copy.deepcopy(triggers),
                            "scrapyard_discard": code == "OGN-020" and was_legion,
                            "replay_optional": code in {"OGN-196", "OGN-226"},
                            "resume_chain": bool(args.get("free_play_parent")),
                        },
                    }
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
                    return
                if code == "OGN-020" and was_legion and row["hand"]:
                    state["decision"] = {"kind": "discard", "player": player,
                                          "remaining": min(2, len(row["hand"])),
                                          "scrapyard_discard": True,
                                          "post_triggers": triggers,
                                          "finalized_card": card}
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
                    return
                if code == "OGN-020" and was_legion:
                    self._draw(state, player, 2, rng)
                self._mark_play_finalized(state, player, card,
                                          trigger_sink=triggers, rng=rng)
                if code in {"OGN-196", "OGN-226"}:
                    self._queue_optional(state, player, "replay_trash_unit",
                                         source=unit["id"], code=code)
                    self._cleanup(state, rng)
                    return
                self._cleanup(state, rng)
                if self._is_field(state, args["location"]) and state["fields"][args["location"]]["controller"] != player:
                    state["battle"] = {"field": args["location"], "attacker": player, "combat": False}
                    state["phase"], state["focus"], state["passes"] = "showdown", player, 0
                self._triggers(state, triggers)
            else:
                spend = args["spend_buff"]
                ignore_cost = bool(args.get("ignore_cost"))
                ignore_energy = bool(args.get("ignore_energy"))
                spell_energy = 0 if spend is not None or ignore_cost or ignore_energy else max(0, data["energy"] - row.get("spell_discount", 0))
                self._pay(row, spell_energy,
                          [] if ignore_cost else args["payment"])
                if spend is None and not ignore_cost and not ignore_energy:
                    row["spell_discount"] = 0
                if spend is not None:
                    self._unit(state, spend)["buff"] = 0
                row["hand"].remove(card)
                effect = ("spell" if implementation and implementation.spell_effect
                          else "return_unit" if code == "OGN-170"
                          else "sabotage" if code == "OGN-156" else "spell")
                triggers = self._second_card_triggers(state, player)
                spell_item = {"effect": effect, "owner": player, "card": card,
                               "card_owner": self._card_owner(state, card, player),
                               "code": code, "targets": args["targets"],
                               "destination": args.get("destination"),
                               "field": args.get("field"),
                               "x": args.get("x", 0),
                               "legion": was_legion,
                               "hidden_field": args.get("hidden_field")}
                if code == "OGN-256":
                    spell_item["fox_fire_initial_targets"] = list(args["targets"])
                if code == "OGN-183":
                    spell_item["deck_options"] = list(args.get("deck_options", []))
                if code in SPELL_CODES:
                    spell_item["post_triggers"] = self._spell_post_triggers(
                        state, player, was_legion)
                    # The spell is already finalized when the Chain item is
                    # created; Ravenbloom/Darius remain post-resolution
                    # triggers and are therefore kept on the item.
                    triggers = []
                self._enter_chain(state, [spell_item])
                # The spell's play process is complete when its Chain item is
                # created.  Its effect may still be pending, but a later card
                # must already see this card as Finalized (including when it
                # is subsequently countered).
                self._mark_play_finalized(state, player, card, item=spell_item)
                self._cleanup(state, rng)
                self._triggers(state, triggers)
        elif kind == "order_triggers":
            pending = list(state.get("pending", []))
            order = list(args.get("order", []))
            if sorted(order) != list(range(len(pending))):
                raise ValueError("trigger order must contain each pending trigger exactly once")
            state.setdefault("ordered_triggers", []).extend(pending[i] for i in order)
            groups = list(state.get("pending_trigger_groups", []))
            if groups:
                next_group = groups.pop(0)
                state["pending_trigger_groups"] = groups
                state["pending"] = next_group
                state["phase"], state["actor"] = (
                    "trigger_order", next_group[0].get("owner", state["turn_player"]))
                state["passes"] = 0
                return
            ordered = state.pop("ordered_triggers", [])
            state["pending"] = []
            state.pop("pending_trigger_groups", None)
            state["phase"] = state["order_return"]
            preserve_context = state.pop("preserve_chain_context", False)
            self._enter_chain(state, ordered, preserve_context=preserve_context)
        elif kind == "begin_move":
            state["selection"] = {"destination": args["destination"], "units": []}
            state["phase"] = "move_select"
        elif kind == "select_unit":
            state["selection"]["units"].append(args["unit"])
        elif kind == "cancel_move":
            state["selection"], state["phase"] = None, "main"
        elif kind == "commit_move":
            destination = state["selection"]["destination"]
            moved = [self._unit(state, uid) for uid in state["selection"]["units"]]
            for unit in moved:
                if unit["code"] == "OGN-185":
                    moved_row = state["players"][player]
                    if moved_row["hand"]:
                        moved_row["trash"].append(moved_row["hand"].pop(0))
                        self._draw(state, player, 1, rng)
            state["selection"], state["phase"] = None, "main"
            self._resolve_move(state, moved, destination, player, rng)
            self._triggers(state, [{"effect": "drummer", "owner": player, "location": destination}
                                   for unit in moved if unit["code"] == "OGN-222" and self._is_field(state, destination)])
        elif kind == "pass":
            state["passes"] += 1
            state["actor"] = 1-player
            if state["passes"] == 2:
                state["passes"] = 0
                if state["phase"] == "chain":
                    self._resolve_chain_item(state, rng)
                else:
                    self._close_showdown(state, rng)
            elif state["phase"] == "showdown":
                state["focus"] = state["actor"]
        elif kind == "assign_damage":
            self._assign_damage(state, args["target"], rng)
        elif kind == "end_turn":
            # End-turn cleanup: lethal first, then heal all, expire all this-turn effects.
            self._cleanup(state, rng)
            # Dazzling Aurora is a mandatory end-of-turn trigger.  Resolve all
            # copies controlled by the active player before resetting turn
            # resources and temporary markers.
            aurora_gears = [gear for gear in list(state["players"][player]["gear"])
                            if gear["code"] == "OGN-160"]
            state["aurora_queue"] = [gear["id"] for gear in aurora_gears]
            state["end_turn_pending"] = {"player": player}
            self._begin_dazzling_aurora(state, player, rng)
        else:
            raise ValueError(f"unknown action {kind}")

    def _finish_end_turn(self, state, player, rng):
        """Finish the end-turn transaction after any Aurora choice windows."""
        for unit in self._units(state, player):
            if unit["code"] == "OGN-073" and self._is_field(state, unit["location"]):
                for rune in state["players"][player]["runes"][:4]:
                    rune["exhausted"] = False
        for unit in state["units"]:
            unit["damage"], unit["temporary"], unit["assault"], unit["stunned"] = 0, 0, 0, False
            unit["temporary_tank"] = False
            unit["kill_on_damage"] = None
            unit["prevent_next_damage"] = 0
        for obj in state["players"]:
            obj["energy"], obj["power"] = 0, []
        for ready_player in state.pop("targon_pending", []):
            for rune in state["players"][ready_player]["runes"][:2]:
                rune["exhausted"] = False
        state["prevent_spell_ability_damage"] = False
        decree = state.get("imperial_decree")
        if decree and decree.get("turn") == state.get("turn"):
            state.pop("imperial_decree", None)
        self._cleanup(state, rng)
        extra_turn = state.pop("extra_turn", None)
        state["turn_player"] = extra_turn if extra_turn is not None else 1-player
        if state["winner"] is None:
            self._start_turn(state, rng)

    def _resolve_chain_item(self, state, rng):
        item = state["chain"].pop()
        completed = self.effects.dispatch(item["effect"], state, item, rng)
        if completed:
            # Ravenbloom Student and other post-spell triggers are created only
            # after the spell has finished resolving.  Keeping them on the
            # spell item prevents them from incorrectly resolving before it.
            post_triggers = item.pop("post_triggers", None)
            if post_triggers:
                played_by = item.get("finalized_by", item.get("played_by", item["owner"]))
                generated = []
                for spec in post_triggers:
                    if spec.get("effect") == "ravenbloom":
                        generated.extend(
                            {"effect": "ravenbloom", "source": source["id"],
                             "owner": played_by}
                            for source in self._units(state, played_by)
                            if source["code"] == "OGN-103"
                        )
                    elif spec.get("effect") == "darius":
                        generated.extend(
                            {"effect": "darius", "source": source["id"],
                             "owner": played_by}
                            for source in self._units(state, played_by)
                            if source["code"] == "OGN-027"
                        )
                    elif spec.get("effect") == "viktor_innovator":
                        generated.extend(
                            {"effect": "viktor_innovator", "source": source["id"],
                             "owner": played_by}
                            for source in self._units(state, played_by)
                            if source["code"] == "OGN-117"
                        )
                    elif spec.get("effect") == "yordle_explorer":
                        source = self._unit(state, spec.get("source"))
                        if (source is not None and source["owner"] == played_by
                                and self._card_implementation(source["code"]) is not None
                                and self._card_implementation(source["code"]).global_effect == "draw_on_power_two"):
                            generated.append({"effect": "yordle_explorer",
                                              "source": source["id"],
                                              "owner": played_by})
                if generated:
                    self._triggers(state, generated, preserve_context=True)
                    if state.get("phase") == "trigger_order":
                        return
            # An effect may queue an optional trigger while resolving.  Keep
            # the explicit optional window open instead of letting chain
            # cleanup overwrite it with the old phase.
            if state.get("phase") == "optional":
                self._cleanup(state, rng)
                return
            self._finish_resolution(state)
            self._cleanup(state, rng)

    def _finish_resolution(self, state):
        if state["chain"]:
            state["phase"] = "chain"
            state["actor"] = state["chain"][-1]["owner"]
            self._arm_chain_top(state)
        elif state.pop("pending_showdown", False):
            state["phase"], state["actor"] = "showdown", state.get("focus", state["turn_player"])
        else:
            state["phase"] = state["chain_return"]
            if state["phase"] == "showdown":
                if state["chain_from_spell"]:
                    state["focus"] = 1-state.get("focus", state.get("actor", state["turn_player"]))
                state["focus"] = state.get("focus", state.get("turn_player", 0))
                state["actor"] = state["focus"]
            elif state["phase"] == "optional" and state.get("optional"):
                state["actor"] = state["optional"][0]["player"]
            else:
                state["actor"] = state["turn_player"]

    def _open_combat_trigger_target(self, state):
        """Finalize designation triggers one at a time before adding them to chain."""
        queue = state.setdefault("combat_trigger_queue", [])
        while queue:
            item = queue.pop(0)
            field = state["battle"]["field"]
            # Twisted Fate must reveal/recycle the top rune before the target
            # is known; its effect opens the domain-specific target window
            # during resolution.  Put the trigger on the Chain without an
            # early designation choice.
            if item.get("effect") in {"ava_attack", "twisted_fate"}:
                item["trigger_target_pending"] = False
                item["trigger_target_finalized"] = True
                state.setdefault("combat_trigger_selected", []).append(item)
                continue
            if item.get("target_required") is False:
                item["trigger_target_pending"] = False
                item["trigger_target_finalized"] = True
                state.setdefault("combat_trigger_selected", []).append(item)
                continue
            targets = [unit["id"] for unit in self._units(state, 1 - item["owner"], field)]
            if not targets:
                continue
            state["decision"] = {
                "kind": "target", "player": item["owner"], "targets": targets,
                "item": item, "resume": "combat_trigger",
                "multi": bool(item.get("target_multi")),
                "min": item.get("target_min", 1), "max": item.get("target_max", 1),
                "selected": [], "allow_repeat": bool(item.get("target_allow_repeat")),
            }
            state["phase"], state["actor"] = "decision", item["owner"]
            return
        selected = state.pop("combat_trigger_selected", [])
        focus = state.get("focus", state.get("turn_player", 0))
        state["phase"], state["actor"], state["passes"] = "showdown", focus, 0
        self._triggers(state, selected)

    def _close_showdown(self, state, rng):
        battle = state["battle"]
        field = battle["field"]
        # Nine-Tailed Fox modifies an enemy attack as it is declared against
        # a battlefield controlled by its legend's player.  The temporary
        # reduction naturally expires in the existing end-turn cleanup.
        if (state["fields"][field]["controller"] == 1 - battle["attacker"]
                and state["players"][1 - battle["attacker"]]["legend"] == "OGN-255"):
            for unit in self._units(state, battle["attacker"], field):
                unit["temporary"] -= 1
        if not battle["combat"] or not self._units(state, 0, field) or not self._units(state, 1, field):
            self._settle_battle(state, rng)
            return
        # Attack triggers that have no player choice resolve before combat damage.
        attackers = self._units(state, battle["attacker"], field)
        defenders = self._units(state, 1-battle["attacker"], field)
        for player, side in ((battle["attacker"], attackers), (1-battle["attacker"], defenders)):
            if len(side) == 1 and any(g["code"] == "OGN-060" for g in state["players"][player]["gear"]):
                side[0]["temporary"] += 1
        if not battle.get("designation_triggers_added"):
            ahri_triggers = [
                {"effect": "ahri_debuff", "source": unit["id"],
                 "owner": unit["owner"], "role": "attacker"}
                for unit in attackers
                if unit["code"] == "OGN-119"
                or (self._card_implementation(unit["code"]) is not None
                    and self._card_implementation(unit["code"]).combat_effect == "ahri_debuff")
            ] + [
                {"effect": "ahri_debuff", "source": unit["id"],
                 "owner": unit["owner"], "role": "defender"}
                for unit in defenders
                if unit["code"] == "OGN-119"
                or (self._card_implementation(unit["code"]) is not None
                    and self._card_implementation(unit["code"]).combat_effect == "ahri_debuff")
            ] + [
                {"effect": "crackshot_target", "source": unit["id"],
                 "owner": unit["owner"]}
                for unit in attackers if unit["code"] == "OGN-130"
            ] + [
                {"effect": "leona_stun_target", "source": unit["id"],
                 "owner": unit["owner"]}
                for unit in attackers if unit["code"] == "OGN-238"
            ] + [
                {"effect": "yasuo_attack_target", "source": unit["id"],
                 "owner": unit["owner"]}
                for unit in attackers if unit["code"] == "OGN-076"
            ] + [
                {"effect": "twisted_fate", "source": unit["id"],
                 "owner": unit["owner"]}
                for unit in attackers if unit["code"] == "OGN-200"
            ]
            ahri_triggers += [
                {"effect": "volibear_attack", "source": unit["id"],
                 "owner": unit["owner"], "field": field,
                 "target_multi": True, "target_min": 5, "target_max": 5,
                 "target_allow_repeat": True}
                for unit in attackers if unit["code"] == "OGN-041"
            ]
            ahri_triggers += [
                {"effect": "teemo_defend", "source": unit["id"],
                 "owner": unit["owner"], "field": field}
                for unit in defenders
                if unit["code"] == "OGN-121"
                or (self._card_implementation(unit["code"]) is not None
                    and self._card_implementation(unit["code"]).global_effect == "teemo_defend")
            ]
            defender_owner = 1 - battle["attacker"]
            for unit in self._units(state, defender_owner):
                implementation = self._card_implementation(unit["code"])
                if (implementation is None
                        or implementation.combat_effect not in {
                            "loyal_pup_defend", "overzealous_fan_defend"}):
                    continue
                if implementation.combat_effect == "loyal_pup_defend":
                    legal_source = unit["location"] == f"base:{defender_owner}"
                else:
                    legal_source = unit["location"] == field
                if legal_source:
                    ahri_triggers.append({
                        "effect": implementation.combat_effect, "source": unit["id"],
                        "owner": defender_owner, "field": field,
                        "target_required": False})
            ahri_triggers += [
                {"effect": "ava_attack", "source": unit["id"],
                 "owner": unit["owner"], "field": field}
                for unit in attackers if unit["code"] == "OGN-107"
            ]
            ahri_triggers += [
                {"effect": "lucian_attack", "source": unit["id"],
                 "owner": unit["owner"], "field": field}
                for unit in attackers if unit["code"] == "SFD-028-221"
            ]
            for unit in attackers + defenders:
                implementation = self._card_implementation(unit["code"])
                if (implementation is not None
                        and implementation.global_effect == "draven_combat_might"):
                    ahri_triggers.append({"effect": "draven_might", "source": unit["id"],
                                          "owner": unit["owner"], "field": field,
                                          "target_required": False})
            battle["designation_triggers_added"] = True
            if ahri_triggers:
                state["combat_trigger_queue"] = ahri_triggers
                state["combat_trigger_selected"] = []
                self._open_combat_trigger_target(state)
                return
        if state["fields"][field]["code"] == "OGN-279" and defenders and not battle.get("fortified_prompted"):
            battle["fortified_prompted"] = True
            owner = 1 - battle["attacker"]
            state["decision"] = {
                "kind": "target", "player": owner,
                "targets": [unit["id"] for unit in defenders],
                "item": {"effect": "fortified_shield", "owner": owner},
                "resume": "close_showdown",
            }
            state["phase"], state["actor"] = "decision", owner
            return
        if state["fields"][field]["code"] == "OGN-285" and defenders:
            if not battle.get("reaver_prompted"):
                battle["reaver_prompted"] = True
                self._queue_optional(state, defenders[0]["owner"], "reaver_recall",
                                     resume="close_showdown")
                return
            defenders = self._units(state, 1-battle["attacker"], field)
        if any(unit["code"] == "OGN-148" for unit in attackers):
            for unit in defenders:
                self._deal_damage(state, unit, 3)
        if any(unit["code"] == "OGN-159" for unit in attackers):
            for unit in defenders:
                if unit["damage"] > 0:
                    unit["damage"] = max(unit["damage"], self.might(state, unit))
        self._cleanup(state, rng)
        if not self._units(state, 0, field) or not self._units(state, 1, field):
            self._settle_battle(state, rng)
            return
        battle["damage"] = {"remaining": [sum(0 if u["stunned"] else max(0, self.might(state, u))
                                               for u in self._units(state, p, field))
                                           for p in (0, 1)], "assignments": [{}, {}],
                         "excess": [0, 0]}
        state["phase"], state["actor"] = "damage", battle["attacker"]
        self._advance_damage(state, rng)

    def _assign_damage(self, state, target_id, rng):
        player = state["actor"]
        damage = state["battle"]["damage"]
        targets = self._units(state, 1-player, state["battle"]["field"])
        assignments = damage["assignments"][player]
        unit = self._unit(state, target_id)
        if unit is None or unit not in targets:
            raise ValueError("invalid damage target")
        unassigned = [u for u in targets if u["id"] not in assignments]
        if unit["code"] == "OGN-068" and any(other["code"] != "OGN-068" for other in unassigned):
            raise ValueError("Caitlyn must be assigned combat damage last")
        # One target choice performs the complete mandatory assignment to that
        # target. It stops at lethal damage while another target remains, and
        # automatically continues with overkill when this is the last target.
        while damage["remaining"][player]:
            pending = assignments.get(target_id, 0)
            lethal_needed = max(0, max(1, self.might(state, unit)) - unit["damage"] - pending)
            amount = min(damage["remaining"][player], lethal_needed) if lethal_needed else damage["remaining"][player]
            if amount <= 0:
                break
            assignments[target_id] = pending + amount
            damage["remaining"][player] -= amount
            other_targets = [u for u in targets if u["id"] != target_id and u["id"] not in assignments]
            if not other_targets:
                damage.setdefault("excess", [0, 0])[player] += amount if not lethal_needed else max(0, amount - lethal_needed)
            if not damage["remaining"][player]:
                break
            if other_targets:
                break
        self._advance_damage(state, rng)

    def _advance_damage(self, state, rng):
        damage = state["battle"]["damage"]
        attacker = state["battle"]["attacker"]
        if damage["remaining"][attacker]:
            state["actor"] = attacker
        elif damage["remaining"][1-attacker]:
            state["actor"] = 1-attacker
        else:
            for allocations in damage["assignments"]:
                for uid, amount in allocations.items():
                    unit = self._unit(state, uid)
                    if unit is None or amount <= 0:
                        continue
                    if unit.get("prevent_next_damage", 0):
                        unit["prevent_next_damage"] = 0
                        continue
                    unit["damage"] += amount
            self._settle_battle(state, rng)

    def _settle_battle(self, state, rng):
        battle = state["battle"]
        field, attacker = battle["field"], battle["attacker"]
        self._cleanup(state, rng)  # Kill lethal before healing, with combat modifiers active.
        combat_draws = []
        if battle["combat"]:
            attackers_alive = bool(self._units(state, attacker, field))
            defenders_alive = bool(self._units(state, 1 - attacker, field))
            if attackers_alive != defenders_alive:
                winning_owner = attacker if attackers_alive else 1 - attacker
                combat_draws.extend(
                    unit["owner"] for unit in self._units(state, winning_owner, field)
                    if (self._card_implementation(unit["code"]) is not None
                        and self._card_implementation(unit["code"]).combat_effect == "draw_one_on_win"))
                for unit in self._units(state, winning_owner, field):
                    implementation = self._card_implementation(unit["code"])
                    if (implementation is not None
                            and implementation.combat_effect == "play_gold_gear"):
                        self._play_gold_gear_token(state, winning_owner, exhausted=True)
                legend = self.card_registry.get(
                    state["players"][winning_owner].get("legend"))
                if (legend is not None
                        and legend.combat_effect == "draw_one_on_win"):
                    combat_draws.append(winning_owner)
        symbol_tie = (battle["combat"]
                      and self._units(state, attacker, field)
                      and self._units(state, 1 - attacker, field)
                      and any(gear["code"] == "OGN-227" and not gear["exhausted"]
                              for gear in state["players"][attacker]["gear"]))
        if battle["combat"]:
            for unit in state["units"]:
                unit["damage"] = 0
                unit["combat_shield"] = 0
            if symbol_tie:
                for unit in self._units(state, location=field):
                    unit["location"] = f"base:{unit['owner']}"
                    unit["exhausted"] = True
            elif self._units(state, 1-attacker, field):
                for unit in self._units(state, attacker, field):
                    unit["location"] = f"base:{attacker}"
        occupants = {u["owner"] for u in self._units(state, location=field)}
        controller = next(iter(occupants)) if len(occupants) == 1 else None
        previous = state["fields"][field]["controller"]
        state["fields"][field]["controller"] = controller
        for owner in combat_draws:
            self._draw(state, owner, 1, rng)
        if (controller == attacker and battle.get("excess", [0, 0])[attacker] >= 5
                and any(unit["code"] == "OGN-034" and unit["owner"] == attacker
                        and unit["location"] == field for unit in state["units"])):
            state["points"][attacker] += 1
        state["battle"], state["phase"], state["actor"] = None, "main", state["turn_player"]
        if controller is not None and controller != previous:
            self._score(state, controller, field, "conquer", rng,
                        uncontrolled=previous is None)
            if state["players"][controller]["legend"] == "OGN-269":
                state["players"][controller]["legend_exhausted"] = False
            # Kai'Sa, Survivor draws once for each copy that conquered this field.
            # Resolve immediately after scoring, matching the simple draw trigger
            # used by this closed card pool.
            kaisa_count = sum(u["code"] == "OGN-039" and u["owner"] == controller
                              for u in self._units(state, controller, field))
            if kaisa_count:
                self._draw(state, controller, kaisa_count, rng)
        self._cleanup(state, rng)

    def observe(self, state, player):
        def card(uid):
            return {"id": uid, "code": state["cards"][uid]["code"]}
        reveal = copy.deepcopy(state.get("reveal"))
        if reveal is not None:
            # Public reveal means every player may look at the front faces.
            # Nocturne's replacement choice belongs to the deck owner, but
            # it does not hide a card that the effect has revealed.
            reveal["cards"] = [card(uid) for uid in reveal.get("cards", [])]
            reveal["selected"] = [card(uid) for uid in reveal.get("selected", [])]
        public_players = []
        for index, row in enumerate(state["players"]):
            public_players.append({"hand_count": len(row["hand"]), "main_count": len(row["main"]),
                                   "rune_deck_count": len(row["rune_deck"]), "runes": copy.deepcopy(row["runes"]),
                                   "energy": row["energy"], "power": row["power"].copy(),
                                   "power_count": len(row["power"]),
                                   "gear": copy.deepcopy(row["gear"]),
                                   "hidden": [{"id": h["id"], "field": h["field"],
                                               "code": h["code"] if player == index else "__back__"}
                                              for h in row.get("hidden", [])],
                                   "legend": row["legend"], "legend_exhausted": row["legend_exhausted"],
                                   "champion": [card(uid) for uid in row["champion"]],
                                   "banishment": [card(uid) for uid in row["banishment"]],
                                   "trash": [card(uid) for uid in row["trash"]],
                                   "played": row["played"],
                                   "finalized_played": row.get("finalized_played", row["played"])})
        return {"player": player, "to_act": state["actor"], "turn_player": state["turn_player"],
                "turn": state["turn"], "phase": state["phase"], "points": state["points"].copy(),
                "victory": state["victory"], "hand": [card(uid) for uid in state["players"][player]["hand"]],
                "players": public_players, "fields": copy.deepcopy(state["fields"]),
                "units": [{**copy.deepcopy(u), "might": self.might(state, u)} for u in state["units"]],
                "chain": copy.deepcopy(state["chain"]), "pending": copy.deepcopy(state["pending"]),
                "optional": copy.deepcopy(state.get("optional", [])),
                "rune_undo_count": (len(state.get("rune_undo", []))
                                     if player == state["actor"] and state["phase"] == "main" else 0),
                "battle": copy.deepcopy(state["battle"]),
                "selection": copy.deepcopy(state["selection"]) if player == state["actor"] else None,
                "decision": ({**copy.deepcopy(state["decision"]),
                              "cards": ([card(state["players"][player]["main"][0])]
                                        if state["decision"]["kind"] == "predict" else [])}
                             if state["decision"] and state["decision"]["player"] == player else None),
                "reveal": reveal,
                "winner": state["winner"]}

    def validate(self, state):
        if state["actor"] not in (0, 1) or state["turn_player"] not in (0, 1):
            raise ValueError("invalid actor")
        optional = state.get("optional", [])
        if state.get("phase") == "optional":
            if not optional or optional[0].get("player") != state["actor"]:
                raise ValueError("invalid optional-effect priority")
        elif optional:
            raise ValueError("optional effects must pause the active phase")
        located = []
        for player, row in enumerate(state["players"]):
            for zone in ("main", "hand", "champion", "trash", "banishment"):
                located.extend(row[zone])
                if any(state["cards"][uid]["owner"] != player for uid in row[zone]):
                    raise ValueError("card in non-owner zone")
            for gear in row.get("gear", []):
                if (gear.get("owner") != player or gear.get("location") != f"base:{player}"
                        or gear.get("card") not in state["cards"]
                        or gear.get("card_owner", state["cards"][gear["card"]]["owner"])
                           != state["cards"][gear["card"]]["owner"]
                        or gear.get("exhausted") not in (True, False)
                        or gear.get("temporary", False) not in (True, False)):
                    raise ValueError("invalid gear state")
                located.append(gear["card"])
            for hidden in row.get("hidden", []):
                if (hidden.get("owner", player) != player or hidden.get("field") not in range(len(state["fields"]))
                        or hidden.get("card") not in state["cards"]):
                    raise ValueError("invalid Hidden card state")
                located.append(hidden["card"])
            runes = row["runes"] + row["rune_deck"]
            if len(runes) != 12 or len({r["id"] for r in runes}) != 12:
                raise ValueError("rune conservation failed")
            if row["energy"] < 0 or any(p not in DOMAINS | {"spell_any"} for p in row["power"]):
                raise ValueError("invalid resource pool")
        located.extend(u["card"] for u in state["units"] if u["card"] is not None)
        located.extend(item["card"] for item in state["chain"]
                       if item.get("card") is not None)
        if state["decision"]:
            item = state["decision"].get("item", {})
            # A spell remains represented by the decision while a target,
            # Divine Judgment zone, or other play-time window is open; count
            # its physical card exactly once even though it is temporarily
            # popped from the Chain during resolution.
            chain_cards = {entry.get("card") for entry in state["chain"]}
            if (item.get("card") is not None and item["card"] not in chain_cards
                    and item["card"] not in located):
                located.append(item["card"])
        reveal = state.get("reveal")
        if reveal is not None:
            if reveal.get("kind") not in {"display", "select"}:
                raise ValueError("invalid reveal state")
            for uid in reveal.get("cards", []):
                if uid not in state["cards"]:
                    raise ValueError("invalid revealed card")
            item = reveal.get("item") or {}
            if item.get("card") is not None and item["card"] not in {entry.get("card") for entry in state["chain"]}:
                located.append(item["card"])
        for item in state.get("optional", []):
            if item.get("effect") == "return_champion" and item.get("candidate") is not None:
                # The candidate remains in its owner's trash until the player
                # accepts the optional return, so conservation still counts it
                # through the normal trash zone.  This branch documents the
                # deferred reference without duplicating the card.
                continue
        if Counter(located) != Counter(state["cards"].keys()):
            raise ValueError("main-deck card conservation failed")
        if len({u["id"] for u in state["units"]}) != len(state["units"]):
            raise ValueError("duplicate object IDs")
        for unit in state["units"]:
            if (unit.get("card") is not None
                    and unit.get("card_owner", state["cards"][unit["card"]]["owner"])
                       != state["cards"][unit["card"]]["owner"]):
                raise ValueError("invalid unit card ownership")
            if (not self._is_field(state, unit["location"])
                    and unit["location"] != f"base:{unit['owner']}"):
                raise ValueError("invalid unit location")
            if (type(unit.get("damage")) is not int or unit["damage"] < 0
                    or type(unit.get("temporary")) is not int
                    or type(unit.get("assault")) is not int or unit["assault"] < 0
                    or type(unit.get("combat_shield")) is not int
                    or unit["combat_shield"] < 0
                    or type(unit.get("buff")) is not int or unit["buff"] < 0
                    or (unit["code"] != "OGN-078" and unit["buff"] not in (0, 1))
                    or type(unit.get("stunned")) is not bool
                    or type(unit.get("temporary_tank")) is not bool):
                raise ValueError("invalid unit state")
        if state["phase"] == "main":
            for field, obj in enumerate(state["fields"]):
                occupants = {u["owner"] for u in self._units(state, location=field)}
                if len(occupants) > 1:
                    raise ValueError("unresolved combat in neutral state")
                if obj["controller"] is not None and obj["controller"] not in occupants:
                    raise ValueError("controller without units")
