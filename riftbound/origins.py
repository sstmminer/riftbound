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
from .engine import Action, canonical
from .effects import EffectRegistry
from .support import ACCELERATE, FIELD_CODES, GEAR_CODES, HIDDEN_CODES, LEGENDS, REACTIONS, RUNES, SPELL_CODES, SPRITE_TOKEN, TOKEN, UNIT_CODES, starter_deck

# Spells with one ordinary unit target and no destination/pairing choice can
# use the same click-to-select target window as the repeated-target spells.
# Legacy expanded actions remain available to non-GUI policies for replay
# compatibility; the GUI can prefer the targeted variant.
SIMPLE_TARGET_SPELLS = frozenset({
    "OGN-004", "OGN-005", "OGN-009", "OGN-014", "OGN-024", "OGN-033",
    "OGN-046", "OGN-050", "OGN-057", "OGN-058", "OGN-069", "OGN-085",
    "OGN-093", "OGN-095", "OGN-102", "OGN-146", "OGN-154",
    "OGN-169", "OGN-172", "OGN-203", "OGN-207", "OGN-213",
    "OGN-229", "OGN-252", "OGN-254", "OGN-262",
})
PAIR_TARGET_SPELLS = frozenset({"OGN-108", "OGN-128", "OGN-209", "OGN-220", "OGN-260"})
DESTINATION_TARGET_SPELLS = frozenset({"OGN-043", "OGN-173", "OGN-250", "OGN-270"})
OPTIONAL_TARGET_SPELLS = frozenset({"OGN-048"})
CONSTRAINED_MULTI_TARGET_SPELLS = frozenset({"OGN-256"})
FIELD_TARGET_SPELLS = frozenset({"OGN-266"})


def card_model(row):
    return Card(row["code"], row["name"], row["type"], frozenset(row["domains"]),
                frozenset(row["tags"]), row["champion"], row["signature"],
                rules_text=row["text"])


class OriginsRules:
    def __init__(self, decks=None, *, extra_fields=()):
        self.cards = {row["code"]: row for row in load_origins()}
        self.effects = self._build_effect_registry()
        self.extra_fields = list(extra_fields)
        if len(self.extra_fields) > 4 or not set(self.extra_fields) <= FIELD_CODES:
            raise ValueError("extra_fields must contain at most four supported battlefield codes")
        self.decks = copy.deepcopy(decks if decks is not None else [starter_deck(), starter_deck()])
        if len(self.decks) != 2:
            raise ValueError("exactly two decks required")
        models = {code: card_model(row) for code, row in self.cards.items()}
        for deck in self.decks:
            validate_deck(Deck(deck["legend"], deck["chosen_champion"], tuple(deck["main"]),
                               tuple(deck["runes"]), tuple(deck["battlefields"])), models)
            require_supported(tuple([deck["legend"], *deck["main"], *deck["runes"], *deck["battlefields"]]))
            if deck["legend"] not in LEGENDS or not set(deck["runes"]) <= RUNES or not set(deck["battlefields"]) <= FIELD_CODES:
                raise ValueError("deck contains unsupported legend, rune or battlefield")
            if any(self.cards[code]["token"] for code in deck["main"]):
                raise ValueError("tokens cannot be included in a constructed main deck")
        digest = hashlib.sha256(canonical({"cards": list(self.cards.values()), "decks": self.decks,
                                           "extra_fields": self.extra_fields}).encode()).hexdigest()
        self.id = f"origins-subset/0.3.0/RUP5-2026-10-09/{digest}"

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
        registry.register("tideturner_target", self._effect_tideturner_target)
        registry.register("ember_hidden_buff", self._effect_ember_hidden_buff)
        registry.register("karthus_deathknell", self._effect_karthus_deathknell)
        registry.register("solari_target", self._effect_solari_target)
        registry.register("ready_self", self._effect_ready_self)
        registry.register("twisted_fate", self._effect_twisted_fate)
        registry.register("draw_one", self._effect_draw_one)
        registry.register("channel_one", self._effect_channel_one)
        registry.register("reaver_recall_target", self._effect_reaver_recall_target)
        registry.register("fortified_shield", self._effect_fortified_shield)
        registry.register("blitz_move", self._effect_blitz_move)
        registry.register("adaptatron_conquer", self._effect_adaptatron_conquer)
        registry.register("return_unit", self._effect_return_unit)
        registry.register("spell", self._effect_spell)
        return registry

    def initial_state(self, rng):
        first = rng.randrange(2)
        state = {"first": first, "turn_player": first, "actor": first, "turn": 0,
                 "phase": "mulligan", "mulligans": 0, "players": [], "cards": {},
                 "units": [], "fields": [], "points": [0, 0], "scored": [[], []],
                 "chain": [], "pending": [], "passes": 0, "battle": None,
                 "beginning_awarded": [False, False], "dreaming_tree_used": [], "selection": None,
                 "decision": None, "optional": [], "optional_return": None,
                 "reveal": None,
                 "optional_ordered": False, "pending_showdown": False,
                 "legend_options": [], "rune_undo": [], "winner": None, "next_object": 0}
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
                                     "turns": 0, "played": 0, "ready_play": False,
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
        location = unit["location"]
        if unit["code"] == "OGN-028":
            value += state["points"][unit["owner"]]
        if unit["code"] == "OGN-109":
            value += len(state["players"][unit["owner"]]["trash"])
        if self._is_field(state, location) and state["fields"][location]["code"] == "OGN-294":
            value += 1
        role = self._role(state, unit)
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
        return max(1, value)

    def _apply_buff(self, state, unit):
        """Apply the ordinary +1 buff, including Stand United's modifier."""
        if unit is None or unit["buff"]:
            return
        unit["buff"] = 1
        bonus = state["players"][unit["owner"]].get("buff_bonus", 0)
        if bonus:
            unit["temporary"] += bonus

    def _radiant_stun_trigger(self, state, player):
        if state["players"][player]["legend"] != "OGN-261":
            return
        friendly = self._units(state, player)
        if friendly:
            self._apply_buff(state, friendly[0])

    def _stun_triggers(self, state, player):
        for source in self._units(state, player):
            if source["code"] == "OGN-059":
                source["exhausted"] = False
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
        return int(unit["code"] in {"OGN-013", "OGN-155", "OGN-161", "OGN-231"} or
                   (unit["code"] == "OGN-232" and self.might(state, unit) >= 5))

    def _ganking(self, state, unit):
        location = unit["location"]
        return ((unit["code"] == "OGN-125" and unit["buff"])
                or (unit["code"] == "OGN-232" and self.might(state, unit) >= 5)
                or unit.get("temporary_ganking", False)
                or (unit["code"] == "OGN-019" and state["players"][unit["owner"]].get("discarded_this_turn"))
                or (unit["code"] in {"OGN-150", "OGN-231"})
                or (self._is_field(state, location) and state["fields"][location]["code"] == "OGN-297"))

    def _tank(self, unit):
        return unit["code"] in {"OGN-054", "OGN-067", "OGN-087", "OGN-137", "OGN-241"} or unit.get("temporary_tank", False)

    def _cleanup(self, state, rng=None):
        for player in (0, 1):
            if state["points"][player] >= state["victory"] and state["points"][player] > state["points"][1-player]:
                state["winner"] = player
                return
        deathknell = []
        deathknell_channel = []
        deathknell_channel_two = []
        deathknell_recycle = []
        kogmaw_fields = []
        viktor_tokens = []
        machine_tokens = []
        while True:
            dead = [u for u in state["units"] if u["damage"] > 0 and u["damage"] >= self.might(state, u)]
            if not dead:
                break
            dead_ids = {u["id"] for u in dead}
            for unit in dead:
                state["units"].remove(unit)
                if unit["card"] is not None:
                    state["players"][unit["owner"]]["trash"].append(unit["card"])
                if unit.get("stunned"):
                    for player in (0, 1):
                        if player != unit["owner"]:
                            shrine = next((g for g in state["players"][player]["gear"]
                                           if g["code"] == "OGN-072" and not g["exhausted"]), None)
                            if shrine is not None:
                                shrine["exhausted"] = True
                                self._draw(state, player, 1, rng if rng is not None else random.Random(0))
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
                    deathknell_recycle.append((unit["owner"], unit["card"]))
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
                    if unit["code"] == "OGN-235"]
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
        state["phase"] = "reveal"
        state["actor"] = state["reveal"]["closer"] if mode == "display" else state["reveal"]["chooser"]
        state["passes"] = 0

    def _finish_reveal(self, state, selected, rng):
        reveal = state.get("reveal")
        if reveal is None:
            raise ValueError("no reveal window is active")
        effect = reveal.get("effect")
        if effect == "sabotage_recycle":
            self._recycle_cards_to_main(state, reveal["owner"], selected,
                                        source="hand", rng=rng)
            item = reveal.get("item")
            if item is not None:
                item["reveal_done"] = True
                state["chain"].append(item)
        elif effect == "dr_mundo_recycle":
            self._recycle_cards_to_main(state, reveal["owner"], selected,
                                        source="trash", rng=rng)
        elif effect == "forge_recycle":
            for owner in (0, 1):
                cards = [uid for uid in selected if uid in state["players"][owner]["trash"]]
                self._recycle_cards_to_main(state, owner, cards, source="trash", rng=rng)
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
                if uid in row["trash"] and state["cards"][uid]["code"] in HIDDEN_CODES:
                    row["trash"].remove(uid)
                    row["hand"].append(uid)
            row["free_hide_turn"] = True
            item = reveal.get("item")
            if item is not None:
                item["reveal_done"] = True
                state["chain"].append(item)
        resume = reveal.get("resume") or {"phase": "main", "actor": state["turn_player"], "passes": 0}
        state["reveal"] = None
        if state.get("chain") or resume["phase"] == "chain":
            state["phase"], state["actor"], state["passes"] = "chain", resume.get("actor", state["actor"]), 0
            self._finish_resolution(state)
        else:
            state["phase"], state["actor"], state["passes"] = resume["phase"], resume["actor"], resume.get("passes", 0)
        self._cleanup(state, rng)

    def _resolve_optional(self, state, item, rng):
        player = item["player"]
        effect = item["effect"]
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
            if target is not None and target["owner"] == player and target["buff"]:
                target["buff"] = 0
                self._draw(state, player, 1, rng)
        elif effect == "ready_runes":
            for rune in state["players"][player]["runes"][:2]:
                rune["exhausted"] = False
        elif effect == "recycle_top_two":
            row = state["players"][player]
            self._recycle_cards_to_main(state, player, list(row["main"][:2]),
                                        source="main", rng=rng)
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

    def _score(self, state, player, field, method, rng):
        board = Scoreboard(state["points"], [set(s) for s in state["scored"]], state["victory"], len(state["fields"]))
        result = board.score(player, field, method=method)
        state["scored"] = [sorted(s) for s in board.scored]
        if result is not None and method == "hold":
            state["points"][player] += sum(u["code"] == "OGN-066"
                                            for u in self._units(state, player, field))
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
                for unit in self._units(state, player, field):
                    if not unit["buff"]:
                        self._apply_buff(state, unit)
                        break
            elif code == "OGN-281" and not state["players"][player]["champion"]:
                chosen = self.decks[player]["chosen_champion"]
                row = state["players"][player]
                candidate = next((uid for uid in row["trash"]
                                  if state["cards"][uid]["code"] == chosen), None)
                if candidate is not None:
                    self._queue_optional(state, player, "return_champion", candidate=candidate)
            elif code == "OGN-286":
                for _ in range(sum(u["code"] == "OGN-039" for u in self._units(state, player, field))):
                    self._draw(state, player, 1, rng)
            elif code == "OGN-293" and len(self._units(state, player, field)) >= 7:
                state["winner"] = player
            elif code == "OGN-288" and state["players"][player]["rune_deck"]:
                self._queue_optional(state, player, "channel_rune")
        if result in {"point", "draw"} and method == "hold":
            for unit in list(self._units(state, player, field)):
                if unit["code"] == "OGN-067":
                    state["units"].remove(unit)
                    if unit.get("card") is not None:
                        state["players"][player]["hand"].append(unit["card"])
        if result in {"point", "draw"} and method == "conquer":
            code = state["fields"][field]["code"]
            if any(unit["code"] == "OGN-155" for unit in self._units(state, player, field)):
                self._queue_optional(state, player, "qiyana_conquer")
            for unit in self._units(state, player, field):
                if unit["code"] == "OGN-056":
                    self._queue_optional(state, player, "adaptatron_conquer", source=unit["id"])
            if code == "OGN-282":
                row = state["players"][player]
                target = next((u for u in self._units(state, player, field) if u["buff"]), None)
                if target is not None:
                    self._queue_optional(state, player, "spend_buff_draw", target=target["id"])
            elif code == "OGN-287":
                self._recycle_one_rune(state, player)
            elif code == "OGN-289":
                self._queue_optional(state, player, "ready_runes")
            elif code == "OGN-291":
                self._queue_optional(state, player, "recycle_top_two")
            elif code == "OGN-298":  # Zaun Warrens
                row = state["players"][player]
                if row["hand"]:
                    row["trash"].append(row["hand"].pop(0))
                    row["discarded_this_turn"] = True
                    self._trigger_jinx_discard(state, player)
                    self._draw(state, player, 1, rng)
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
        state["dreaming_tree_used"] = [False] * len(state["fields"])
        for row in state["players"]:
            row["played"] = 0
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
                if unit["card"] is not None:
                    row["trash"].append(unit["card"])
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
        for field, obj in enumerate(state["fields"]):
            if obj["controller"] == player:
                self._score(state, player, field, "hold", rng)
                if state["winner"] is not None:
                    return
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
                if code not in HIDDEN_CODES:
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
        kind = "play_unit" if self.cards[code]["type"] == "unit" else "play_spell"
        if kind == "play_unit":
            nested = Action.make(kind, card=hidden["card"], location=hidden["field"],
                                  accelerate=False, payment=[],
                                  enter_target=(targets[0] if targets else None),
                                  ignore_cost=True, hidden_field=hidden["field"])
        else:
            nested = Action.make(kind, card=hidden["card"], targets=list(targets),
                                 destination=None, spend_buff=None, payment=[],
                                 ignore_cost=True, hidden_field=hidden["field"])
        self.apply(state, nested, rng)

    def _gear_actions(self, state):
        """Play supported gear to the controller's Base and expose simple abilities."""
        player = state["actor"]
        row = state["players"][player]
        result = []
        if state["phase"] == "main" and not self._cards_locked(state, player):
            for card in row["hand"]:
                code = state["cards"][card]["code"]
                if code not in GEAR_CODES:
                    continue
                data = self.cards[code]
                for payment in self._payments(state, player, data["energy"], data["domains"],
                                               data["power_cost"]):
                    result.append(Action.make("play_gear", card=card, payment=payment))
        gear_resource = {"OGN-040": "fury", "OGN-081": "calm", "OGN-120": "mind",
                         "OGN-163": "body", "OGN-204": "chaos", "OGN-245": "order"}
        for gear in row["gear"]:
            if gear["exhausted"]:
                continue
            if gear["code"] in gear_resource:
                result.append(Action.make("gear_resource", gear=gear["id"], domain=gear_resource[gear["code"]]))
            elif gear["code"] == "OGN-098":
                result.append(Action.make("gear_resource", gear=gear["id"], energy=1))
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
        if row["legend"] == "OGN-253" and not row["legend_exhausted"] and row["played"]:
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
            if code not in SPELL_CODES or (state["phase"] == "chain" and code not in REACTIONS):
                continue
            if code == "OGN-008" and not row["hand"]:
                continue
            data = self.cards[code]
            targeted_only = code in {"OGN-029", "OGN-104", "OGN-183", "OGN-248"}
            if code in FIELD_TARGET_SPELLS or code == "OGN-268":
                energy = max(0, data["energy"] - row.get("spell_discount", 0))
                for payment in self._payments(state, player, energy, data["domains"], data["power_cost"], spell=True):
                    result.append(Action.make("play_field_targeted", card=card,
                                              fields=list(range(len(state["fields"]))),
                                              x_choice=code == "OGN-268", payment=payment))
            if code in {"OGN-022", "OGN-047", "OGN-083", "OGN-114", "OGN-123", "OGN-129", "OGN-133", "OGN-134", "OGN-138", "OGN-144", "OGN-145", "OGN-153", "OGN-071", "OGN-156", "OGN-170", "OGN-179", "OGN-183", "OGN-187", "OGN-237", "OGN-198", "OGN-248", "OGN-264", "OGN-268", "OGN-201", "OGN-221", "OGN-224", "OGN-233"}:
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
                           if self._is_field(enemy["location"])]
            elif code == "OGN-266":
                targets = [[u["id"]] for u in state["units"] if self._is_field(u["location"])]
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
                field_units = [u["id"] for u in state["units"] if self._is_field(state, u["location"])]
                targets = [[]] + [[uid] for uid in field_units]
                targets += [list(pair) for pair in combinations(field_units, 2)]
            elif code == "OGN-029":
                targets = [[a, b] for a in [u["id"] for u in state["units"]]
                           for b in [u["id"] for u in state["units"]]]
            elif code == "OGN-206":
                targets = [list(pair) for pair in combinations([u["id"] for u in self._units(state, player)], 2)]
            elif code == "OGN-046":
                targets = [[u["id"]] for u in self._units(state, player)]
            elif code in {"OGN-014"}:
                targets = [[u["id"]] for u in state["units"] if self._is_field(state, u["location"])]
            else:
                targets = [[u["id"]] for u in state["units"]
                           if code not in {"OGN-005", "OGN-009", "OGN-014", "OGN-024", "OGN-085", "OGN-105"}
                           or self._is_field(state, u["location"])]
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
                if code in {"OGN-043", "OGN-173", "OGN-250", "OGN-270"}:
                    unit = self._unit(state, selected[0])
                    destinations = [f"base:{unit['owner']}", *range(len(state["fields"]))]
                    destinations = [destination for destination in destinations
                                    if destination != unit["location"]]
                deflect = sum(self._deflect(state, self._unit(state, uid)) for uid in selected
                              if self._unit(state, uid)["owner"] != player)
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
                            if code in (SIMPLE_TARGET_SPELLS | PAIR_TARGET_SPELLS | DESTINATION_TARGET_SPELLS | OPTIONAL_TARGET_SPELLS | CONSTRAINED_MULTI_TARGET_SPELLS | {"OGN-029", "OGN-104", "OGN-105", "OGN-183", "OGN-206", "OGN-248"}) and not targeted_added:
                                candidates = ([u["id"] for u in self._units(state, player)]
                                              if code == "OGN-104" else
                                              list(row["main"][:3])
                                              if code == "OGN-183" else
                                              [u["id"] for u in state["units"]]
                                              if code == "OGN-029" else
                                              sorted({uid for pair in targets for uid in pair})
                                              if code in PAIR_TARGET_SPELLS else
                                              sorted({selected[0] for selected in targets if selected})
                                              if code in OPTIONAL_TARGET_SPELLS else
                                              sorted({u["id"] for u in state["units"] if self._is_field(state, u["location"])})
                                              if code in CONSTRAINED_MULTI_TARGET_SPELLS else
                                              sorted({selected[0] for selected in targets if selected})
                                              if code in DESTINATION_TARGET_SPELLS else
                                              sorted({selected[0] for selected in targets if selected})
                                              if code in SIMPLE_TARGET_SPELLS else
                                              [u["id"] for u in state["units"]
                                               if self._is_field(state, u["location"])]
                                               if code in {"OGN-105", "OGN-248"} else
                                              [u["id"] for u in self._units(state, player)])
                                target_count = (6 if code == "OGN-248" else
                                                2 if code in (PAIR_TARGET_SPELLS | {"OGN-029", "OGN-206"}) else
                                                1 if code in (SIMPLE_TARGET_SPELLS | {"OGN-104", "OGN-183"}) else
                                                1 if code in DESTINATION_TARGET_SPELLS else
                                                0)
                                target_pairs = [list(pair) for pair in targets] if code in PAIR_TARGET_SPELLS else None
                                target_min = (0 if code in (OPTIONAL_TARGET_SPELLS | CONSTRAINED_MULTI_TARGET_SPELLS)
                                              else target_count if code != "OGN-105" else 0)
                                target_max = (1 if code in OPTIONAL_TARGET_SPELLS else
                                              len(candidates) if code in CONSTRAINED_MULTI_TARGET_SPELLS else
                                              target_count if code not in {"OGN-105", "OGN-206"} else 2)
                                result.append(Action.make(
                                    "play_spell_targeted", card=card,
                                    target_candidates=candidates,
                                    target_min=target_min,
                                    target_max=target_max,
                                    allow_repeat=code in {"OGN-029", "OGN-248"},
                                    target_pairs=target_pairs,
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
            if code not in UNIT_CODES:
                continue
            data = self.cards[code]
            permitted = locations.copy()
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
            energy = data["energy"] - (2 if code == "OGN-012" and row["played"] else 0)
            if "Dragon" in data["tags"] and any(u["code"] == "OGN-140" and u["owner"] == player
                                                  and self._is_field(u["location"]) for u in state["units"]):
                energy = max(1, energy - 2)
            if code == "OGN-195":
                energy = max(1, energy - len(row["trash"]))
            sacrifices = ([unit["id"] for unit in self._units(state, player)]
                          if code == "OGN-208" else [None])
            extra_costs = ([False, True] if code == "OGN-044" and row["energy"] >= energy else [False])
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
                                    total_energy = max(0, energy - (2 if discard_card else 0))
                                    total_energy += int(additional_cost)
                                    total_power = max(0, data["power_cost"] - len(spend_buffs) - len(kill_units))
                                    for payment in self._payments(state, player, total_energy, data["domains"], total_power):
                                        for location in permitted:
                                            enter_targets = [None]
                                            if code == "OGN-016" and row["played"]:
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
                                                    spend_buffs=spend_buffs,
                                                    kill_units=kill_units))
                                            if code == "OGN-016" and row["played"] and candidates:
                                                result.append(Action.make(
                                                    "play_unit_targeted", card=card, location=location,
                                                    accelerate=accelerate, payment=payment,
                                                    additional_cost=additional_cost, sacrifice=sacrifice,
                                                    target_candidates=candidates))
        return result

    def _movable(self, state, destination):
        player = state["actor"]
        base = f"base:{player}"
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
        origins = {unit["id"]: unit["location"] for unit in moved}
        for unit in moved:
            if unit["owner"] != initiator and not from_effect:
                raise ValueError("cannot move an enemy unit with a normal move")
            origin = origins[unit["id"]]
            if (destination == f"base:{unit['owner']}" and self._is_field(state, origin)
                    and state["fields"][origin]["code"] == "OGN-295"):
                raise ValueError("Vilemaw's Lair prevents moving to base")
            unit["location"], unit["exhausted"] = destination, not ready
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
        # Stealthy Pursuer follows a friendly move from its location.  The
        # closed engine resolves the optional choice as accepted when the
        # pursuer is ready; an exhausted pursuer remains in place.
        moved_ids = {unit["id"] for unit in moved}
        friendly_origins = {origins[unit["id"]] for unit in moved if unit["owner"] == initiator}
        for watcher in list(self._units(state, initiator)):
            if (watcher["code"] == "OGN-177" and watcher["id"] not in moved_ids
                    and not watcher["exhausted"] and watcher["location"] in friendly_origins):
                watcher["location"], watcher["exhausted"] = destination, True
                watcher["move_count"] = watcher.get("move_count", 0) + 1
        self._cleanup(state, rng)
        if not self._is_field(state, destination):
            return False
        enemies = self._units(state, 1 - initiator, destination)
        if state["fields"][destination]["controller"] == initiator and not enemies:
            return False
        state["battle"] = {"field": destination, "attacker": initiator,
                            "combat": bool(enemies)}
        state["focus"], state["passes"] = initiator, 0
        if from_effect:
            # A spell/ability resolving on the chain resumes into showdown;
            # an ability activated directly during Main moves there now.
            if state["phase"] == "chain":
                state["pending_showdown"] = True
            else:
                state["phase"], state["actor"] = "showdown", initiator
        else:
            state["phase"], state["actor"] = "showdown", initiator
        return True

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
            if decision["kind"] == "choice":
                actions = [Action.make("choose_option", option=option)
                           for option in decision.get("options", [])]
                # Accelerate is paid during the play transaction.  Basic rune
                # Add-resource reactions remain available in this narrow
                # window so the player can exhaust/recycle runes before
                # confirming the additional cost; no other main-phase action
                # is exposed while the unit entry is pending.
                if decision.get("accelerate"):
                    row = state["players"][player]
                    domains = set(decision["accelerate"].get("domains", []))
                    can_energy = row["energy"] >= 1 or any(not rune["exhausted"] for rune in row["runes"])
                    can_power = any(power in domains or power == "any" for power in row["power"]) or any(
                        domains.intersection(self.cards[rune["code"]]["domains"])
                        for rune in row["runes"])
                    if not (can_energy and can_power):
                        actions = [action for action in actions
                                   if json.loads(action.arguments).get("option") != "accelerate"]
                    for rune in row["runes"]:
                        if not rune["exhausted"]:
                            actions.append(Action.make("exhaust_rune", rune=rune["id"]))
                        actions.append(Action.make("recycle_rune", rune=rune["id"]))
                return tuple(actions)
            if decision["kind"] == "predict":
                return (Action.make("predict", recycle=False), Action.make("predict", recycle=True))
            if decision["kind"] == "field":
                return tuple(Action.make("choose_field", field=field)
                             for field in decision.get("fields", []))
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
        if not state["chain"] and not preserve_context:
            state["chain_return"] = state["phase"]
            state["chain_from_spell"] = any(item["effect"] == "spell" for item in items)
        state["chain"].extend(items)
        state["phase"], state["actor"], state["passes"] = "chain", items[-1]["owner"], 0
        self._arm_chain_top(state)

    def _triggers(self, state, triggers):
        if not triggers:
            return
        if len(triggers) == 1:
            self._enter_chain(state, triggers)
        else:
            state["pending"] = triggers
            state["order_return"] = state["phase"]
            state["phase"], state["actor"] = "trigger_order", triggers[0]["owner"]

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
        if effect == "return_unit_trigger":
            return [uid for uid in state["players"][owner]["trash"]
                    if self.cards[state["cards"][uid]["code"]]["type"] == "unit"]
        if effect == "solari_target":
            return [u["id"] for u in state["units"] if u["owner"] != owner]
        if effect == "buff_two":
            return [u["id"] for u in self._units(state, owner) if u["id"] != source]
        if effect == "kinkou_buff":
            return [u["id"] for u in self._units(state, owner) if u["id"] != source]
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
        if effect == "move_field_unit":
            return [u["id"] for u in state["units"] if self._is_field(state, u["location"])]
        if effect == "tideturner_target":
            original = item.get("original_location")
            return [u["id"] for u in self._units(state, owner)
                    if u["id"] != source and u["location"] != original]
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
            if not targets and not item.get("target_multi"):
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
                "min": 0 if item.get("target_multi") else 1,
                "max": 2 if item.get("target_multi") else 1,
                "selected": [],
            }
            state["phase"], state["actor"] = "decision", item["owner"]
            state["passes"] = 0
            return True
        return False

    def _new_unit(self, state, code, owner, location, *, card=None, exhausted=None):
        if exhausted is None:
            exhausted = not any(u["code"] == "OGN-011" for u in self._units(state, owner))
        unit = {"id": self._object(state), "card": card, "code": code, "owner": owner,
                "location": location, "exhausted": exhausted, "buff": 0,
                "temporary": 0, "temporary_unit": False, "temporary_ganking": False,
                "temporary_tank": False, "combat_shield": 0, "assault": 0,
                "udyr_choices": [],
                "damage": 0, "stunned": False, "move_count": 0,
                "kill_on_damage": None}
        state["units"].append(unit)
        return unit

    def _second_card_triggers(self, state, player):
        if state["players"][player]["played"] != 2:
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
        state["phase"], state["actor"], state["passes"] = "main", player, 0
        row = state["players"][player]
        if pending.get("scrapyard_discard") and row["hand"]:
            state["decision"] = {"kind": "discard", "player": player,
                                  "remaining": min(2, len(row["hand"])),
                                  "scrapyard_discard": True,
                                  "post_triggers": triggers}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
            return
        if pending.get("scrapyard_discard"):
            self._draw(state, player, 2, rng)
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
            source["exhausted"] = False
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
            self._players_hand(state, target["owner"]).append(card)
        return True

    def _players_hand(self, state, player):
        return state["players"][player]["hand"]

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
        return gear

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
        if state["players"][owner]["main"]:
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

    def _open_target_choice(self, state, item, targets, *, multi=False, minimum=1, maximum=None):
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
        maximum = len(target_ids) if maximum is None else min(maximum, len(target_ids))
        if multi and maximum < minimum:
            return True
        decision = {"kind": "target", "player": item["owner"],
                    "targets": target_ids, "item": item}
        if multi:
            decision.update({"multi": True, "min": minimum, "max": maximum, "selected": []})
        state["decision"] = decision
        state["phase"], state["actor"] = "decision", item["owner"]
        return False

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
            target["exhausted"] = False
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
            source["exhausted"] = False
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
        source["exhausted"] = False
        return True

    def _effect_jinx_discard(self, state, item, rng):
        source = self._unit(state, item.get("source"))
        if source is not None and source["owner"] == item["owner"]:
            source["exhausted"] = False
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
            state["players"][item["owner"]]["trash"].append(gear["card"])
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
                state["players"][owner]["trash"].append(item["card"])
                return True
            return self._open_target_choice(state, item, targets)
        trash = state["players"][owner]["trash"]
        if item["target"] in trash:
            trash.remove(item["target"])
            state["players"][owner]["hand"].append(item["target"])
        state["players"][owner]["trash"].append(item["card"])
        return True

    def _effect_spell(self, state, item, rng):
        code, owner = item["code"], item["owner"]
        returned = []
        killed_by_hidden_blade = None
        state.setdefault("dreaming_tree_used", [False] * len(state["fields"]))
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
        for uid in item["targets"]:
            unit = self._unit(state, uid)
            if unit is None or (code in {"OGN-005", "OGN-009", "OGN-014", "OGN-024", "OGN-085", "OGN-105"}
                                and not self._is_field(state, unit["location"])):
                continue
            if code == "OGN-237":
                unit["damage"] = max(unit["damage"], self.might(state, unit))
            elif code == "OGN-187":
                if unit["card"] is not None:
                    state["units"].remove(unit)
                    state["players"][unit["owner"]]["hand"].append(unit["card"])
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
                    unit["owner"] = owner
                    unit["location"] = f"base:{owner}"
                    unit["exhausted"] = True
            elif code == "OGN-053":
                state["players"][owner]["buff_bonus"] = 1
                self._apply_buff(state, unit)
            elif code == "OGN-069":
                # Last Stand doubles the unit's current Might for this turn;
                # the temporary marker is removed at the next Beginning Phase.
                unit["temporary"] += self.might(state, unit)
                unit["temporary_unit"] = True
            elif code == "OGN-180":
                unit["temporary_unit"] = True
            elif code in {"OGN-206", "OGN-207"}:
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
                unit["temporary"] += 1
                if len(self._units(state, owner, unit["location"])) == 1:
                    unit["temporary"] += 1
            elif code in {"OGN-104", "OGN-169", "OGN-172"}:
                returned.append(unit)
            elif code == "OGN-213":
                killed_by_hidden_blade = unit["owner"]
                unit["damage"] = max(unit["damage"], self.might(state, unit))
            elif code == "OGN-220":
                unit["stunned"] = True
            elif code == "OGN-146":
                unit["exhausted"] = False
            elif code == "OGN-252":
                self._deal_damage(state, unit, 5)
            elif code == "OGN-033":
                self._deal_damage(state, unit, 6)
            elif code == "OGN-262":
                if self._is_field(state, unit["location"]):
                    unit["stunned"] = True
            elif code == "OGN-266" and item.get("field") is None:
                field = unit["location"]
                for friendly in self._units(state, owner, field):
                    friendly["temporary"] += 1
                for enemy in self._units(state, 1-owner, field):
                    enemy["temporary"] -= 1
            elif code == "OGN-108" and item["targets"] and item["targets"][0] == uid:
                if len(item["targets"]) >= 2:
                    other = self._unit(state, item["targets"][1])
                    if other is not None and other["owner"] == owner:
                        unit["temporary"] += self.might(state, other) - self.might(state, unit)
            elif code == "OGN-128" and item["targets"] and item["targets"][0] == uid and len(item["targets"]) >= 2:
                other = self._unit(state, item["targets"][1])
                if other is not None:
                    self._deal_damage(state, unit, self.might(state, other))
                    self._deal_damage(state, other, self.might(state, unit))
            elif code == "OGN-209":
                unit["damage"] = max(unit["damage"], self.might(state, unit))
            elif code == "OGN-260" and item["targets"] and item["targets"][0] == uid and len(item["targets"]) >= 2:
                unit["exhausted"] = False
                other = self._unit(state, item["targets"][1])
                if other is not None:
                    self._deal_damage(state, other, self.might(state, unit))
        for unit in returned:
            if unit not in state["units"]:
                continue
            state["units"].remove(unit)
            card = unit["card"]
            if card is not None:
                row = state["players"][unit["owner"]]
                if card in row["champion"]:
                    row["champion"].remove(card)
                row["hand"].append(card)
            if code == "OGN-104":
                self._channel_rune(state, unit["owner"], exhausted=True)
        if code == "OGN-048":
            if item["targets"]:
                target = self._unit(state, item["targets"][0])
                if target is not None:
                    target["exhausted"] = True
            self._draw(state, owner, 2 if item["targets"] else 1, rng)
        elif code == "OGN-144":
            self._draw(state, owner, 2, rng)
        elif code == "OGN-224":
            self._draw(state, owner, 1, rng)
        elif code == "OGN-198":
            row = state["players"][owner]
            candidate = next((uid for uid in row["trash"]
                              if self.cards[state["cards"][uid]["code"]]["type"] == "unit"), None)
            if candidate is not None:
                row["trash"].remove(candidate)
                self._new_unit(state, state["cards"][candidate]["code"], owner,
                               f"base:{owner}", card=candidate, exhausted=True)
        elif code == "OGN-022":
            for player in (0, 1):
                for gear in list(state["players"][player]["gear"]):
                    state["players"][player]["gear"].remove(gear)
                    state["players"][player]["trash"].append(gear["card"])
        elif code == "OGN-179":
            for player in (0, 1):
                gears = state["players"][player]["gear"]
                if gears:
                    state["players"][player]["trash"].append(gears.pop(0)["card"])
        elif code == "OGN-145":
            state["prevent_spell_ability_damage"] = True
        elif code == "OGN-153":
            for unit in self._units(state, owner):
                if unit["buff"]:
                    unit["buff"] = 0
                    unit["exhausted"] = False
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
                       if state["cards"][uid]["code"] in HIDDEN_CODES]
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
        for uid in item["targets"]:
            target = self._unit(state, uid)
            if (target is not None and target["owner"] == owner and self._is_field(state, target["location"])
                    and state["fields"][target["location"]]["code"] == "OGN-292"
                    and not state["dreaming_tree_used"][target["location"]]):
                state["dreaming_tree_used"][target["location"]] = True
                self._draw(state, owner, 1, rng)
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
        state["players"][owner]["trash"].append(item["card"])
        if code == "OGN-008" and item.get("discarded_card") is not None:
            self._trigger_jinx_discard(state, owner)
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
                # A display-only effect still has to complete the card that
                # opened the window (including post-spell triggers).  The
                # chain resolver had popped that item before opening the
                # reveal, so put it back on top and mark the reveal complete.
                item = reveal.get("item")
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
        if kind == "choose_field":
            decision = state.get("decision")
            field = args.get("field")
            if (not decision or decision.get("kind") != "field"
                    or field not in decision.get("fields", [])):
                raise ValueError("field target selection is unavailable")
            item = decision["item"]
            item["field"] = field
            if decision.get("x_choice"):
                state["decision"] = {"kind": "choice", "player": player,
                                      "options": list(range(decision.get("x_max", 0) + 1)),
                                      "item": item, "x_choice": True}
                state["phase"], state["actor"], state["passes"] = "decision", player, 0
                return
            state["decision"] = None
            state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
            return
        if kind in {"predict", "discard_card", "choose_target", "confirm_targets", "cancel_play", "choose_option"}:
            if kind == "choose_option":
                decision = state.get("decision")
                if not decision or decision.get("kind") != "choice" or args.get("option") not in decision.get("options", []):
                    raise ValueError("invalid choice option")
                option = args["option"]
                if decision.get("x_choice"):
                    item = decision["item"]
                    x = int(option)
                    if x < 0 or x > len(row["power"]):
                        raise ValueError("invalid X payment")
                    self._pay(row, 0, list(range(x)))
                    item["x"] = x
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "chain", item["owner"], 0
                    return
                if decision.get("destination_choice"):
                    item = decision["item"]
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
                        power_index = next((index for index, power in enumerate(row["power"])
                                            if power in domains or power == "any"), None)
                        if row["energy"] < 1 or power_index is None:
                            raise ValueError("Accelerate requires 1 energy and one matching domain power")
                        row["energy"] -= 1
                        row["power"].pop(power_index)
                        # 805.6: the replacement makes the unit enter ready;
                        # this is not a separate 'becomes ready' event.
                        unit["exhausted"] = False
                    state["decision"] = None
                    self._finish_unit_play(state, pending, rng)
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
                        source["exhausted"] = False
                    elif option == "ganking":
                        source["temporary_ganking"] = True
                    source.setdefault("udyr_choices", []).append(option)
                    state["decision"] = None
                    state["phase"], state["actor"], state["passes"] = "main", player, 0
                    self._cleanup(state, rng)
                    return
                if decision.get("party_favors"):
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
                if decision.get("scrapyard_discard"):
                    decision["remaining"] -= 1
                    if decision["remaining"]:
                        return
                    self._draw(state, player, 2, rng)
                    post = decision.get("post_triggers", [])
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
            elif kind == "choose_target":
                decision = state["decision"]
                if args["target"] not in decision["targets"]:
                    raise ValueError("invalid target choice")
                if decision.get("destination_select"):
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
                    else:
                        raise ValueError("unknown destination target")
                    destinations = [destination for destination in destinations
                                    if destination != target["location"]]
                    if not destinations:
                        raise ValueError("no legal destination")
                    item["targets"] = [args["target"]]
                    state["decision"] = {
                        "kind": "choice", "player": player,
                        "options": destinations, "item": item,
                        "destination_choice": True,
                    }
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
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
                            if target.get("card") is not None:
                                row["trash"].append(target["card"])
                        else:
                            gear = next((g for g in row["gear"] if g["id"] == args["target"]), None)
                            if gear is None:
                                raise ValueError("Malzahar target is unavailable")
                            row["gear"].remove(gear)
                            row["trash"].append(gear["card"])
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
                            if target.get("card") is not None:
                                row["hand"].append(target["card"])
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
                if decision.get("play_hidden_targeted"):
                    info = decision["hidden"]
                    state["decision"] = None
                    self._play_hidden_from_decision(state, player, info, selected, rng)
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
        elif kind == "play_gear":
            card = args["card"]
            code = state["cards"][card]["code"]
            if code not in GEAR_CODES or card not in row["hand"]:
                raise ValueError("unsupported gear")
            data = self.cards[code]
            self._pay(row, data["energy"], args["payment"])
            row["hand"].remove(card)
            row["played"] += 1
            row["gear"].append({"id": card, "card": card, "code": code,
                                "owner": player, "location": f"base:{player}",
                                "exhausted": code == "OGN-017"})
            if code == "OGN-182":
                self._draw(state, player, 1, rng)
            elif code == "OGN-212":
                self._new_unit(state, TOKEN, player, f"base:{player}", exhausted=False)
            for unit in self._units(state, player):
                if unit["code"] == "OGN-091":
                    unit["exhausted"] = False
            state["passes"] = 0
        elif kind == "hide_card":
            card = args["card"]
            code = state["cards"][card]["code"]
            field = args["field"]
            if code not in HIDDEN_CODES or field not in range(len(state["fields"])):
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
            kind2 = "play_unit" if self.cards[code]["type"] == "unit" else "play_spell"
            if kind2 == "play_unit":
                nested = Action.make(kind2, card=hidden["card"], location=hidden["field"],
                                     accelerate=False, payment=[], enter_target=None,
                                     ignore_cost=True, hidden_field=hidden["field"])
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
                                  "multi": args.get("target_max", 1) > 1,
                                  "min": args.get("target_min", 1),
                                  "max": args.get("target_max", 1), "selected": [],
                                  "target_pairs": [list(pair) for pair in args.get("target_pairs", [])],
                                  "item": {"effect": "hidden_play", "owner": player},
                                  "play_hidden_targeted": True,
                                  "hidden": {"card": hidden["id"], "field": hidden["field"],
                                             "code": hidden["code"]}}
            state["phase"], state["actor"] = "decision", player
        elif kind == "gear_resource":
            gear = next((g for g in row["gear"] if g["id"] == args["gear"]), None)
            if gear is None or gear["exhausted"]:
                raise ValueError("gear resource is unavailable")
            gear["exhausted"] = True
            if args.get("energy"):
                row["energy"] += int(args["energy"])
            else:
                row["power"].append(args["domain"])
            state["passes"] = 0
        elif kind == "gear_targeted":
            gear = next((g for g in row["gear"] if g["id"] == args["gear"]), None)
            if (gear is None or gear["exhausted"]
                    or args.get("effect") not in {"gear_debuff", "gear_buff_exhausted", "gear_move"}):
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
            row["trash"].append(gear["card"])
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
            row["trash"].append(gear["card"])
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
            row["legend_exhausted"] = True
            row["energy"] += 1
            state["passes"] = 0
        elif kind == "legend_spell_power":
            row["legend_exhausted"] = True
            row["power"].append("spell_any")
            state["passes"] = 0
        elif kind == "unit_udyr":
            source = self._unit(state, args["unit"])
            if (source is None or source["owner"] != player or source["code"] != "OGN-157"
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
                valid = (source["code"] == "OGN-068" and self._is_field(state, source["location"])
                         and any(self._is_field(state, u["location"]) for u in state["units"]))
            elif ability == "malzahar":
                valid = source["code"] == "OGN-113"
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
            if source is None or source["owner"] != player or source["code"] != "OGN-113" or source["exhausted"]:
                raise ValueError("Malzahar ability is unavailable")
            target = self._unit(state, args["target"])
            if target is not None:
                if target["owner"] != player:
                    raise ValueError("Malzahar requires a friendly target")
                state["units"].remove(target)
                if target.get("card") is not None:
                    row["trash"].append(target["card"])
            else:
                gear = next((g for g in row["gear"] if g["id"] == args["target"]), None)
                if gear is None:
                    raise ValueError("Malzahar target is unavailable")
                row["gear"].remove(gear)
                row["trash"].append(gear["card"])
            source["exhausted"] = True
            row["power"].extend(["spell_any", "spell_any"])
            state["passes"] = 0
        elif kind == "unit_caitlyn":
            unit = self._unit(state, args["unit"])
            target = self._unit(state, args["target"])
            if (unit is None or unit["owner"] != player or unit["code"] != "OGN-068"
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
            if unit is None or unit["owner"] != player or unit["code"] != "OGN-078" or unit["exhausted"]:
                raise ValueError("Lee Sin ability is unavailable")
            unit["exhausted"] = True
            unit["buff"] = unit["buff"] + 1
            state["passes"] = 0
        elif kind == "unit_recycle_buff":
            unit = self._unit(state, args["unit"])
            if unit is None or unit["owner"] != player or unit["code"] != "OGN-036" or unit["exhausted"]:
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
                if unit.get("card") is not None:
                    row["hand"].append(unit["card"])
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
            row["played"] += 1
            item = {"effect": "spell", "owner": player, "card": card,
                    "code": code, "targets": [], "field": None,
                    "legion": row["played"] > 1,
                    "x": 0,
                    "post_triggers": [{"effect": "ravenbloom", "owner": player}]}
            if row["played"] == 2:
                item["post_triggers"].append({"effect": "darius", "owner": player})
            if state["turn_player"] != player:
                item["post_triggers"].extend(
                    {"effect": "viktor_innovator", "source": source["id"], "owner": player}
                    for source in self._units(state, player) if source["code"] == "OGN-117")
            self._enter_chain(state, [item])
            state["decision"] = {"kind": "field", "player": player,
                                  "fields": list(args.get("fields", [])), "item": item,
                                  "x_choice": bool(args.get("x_choice", False)),
                                  "x_max": len(row["power"]) if args.get("x_choice") else 0}
            state["phase"], state["actor"], state["passes"] = "decision", player, 0
        elif kind == "play_spell_targeted":
            card = args["card"]
            code = state["cards"][card]["code"]
            if code not in (SIMPLE_TARGET_SPELLS | PAIR_TARGET_SPELLS | DESTINATION_TARGET_SPELLS | OPTIONAL_TARGET_SPELLS | CONSTRAINED_MULTI_TARGET_SPELLS | {"OGN-029", "OGN-104", "OGN-105", "OGN-183", "OGN-206", "OGN-248"}) or card not in row["hand"]:
                raise ValueError("target-selection spell is unavailable")
            data = self.cards[code]
            payment = args.get("payment", [])
            spend = args.get("spend_buff")
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
            row["played"] += 1
            item = {"effect": "spell", "owner": player, "card": card,
                    "code": code, "targets": [], "destination": args.get("destination"),
                    "legion": before["played"] > 0}
            if code == "OGN-183":
                item["deck_options"] = list(args.get("deck_options", []))
            # Ravenbloom triggers after this spell finishes resolving.
            item["post_triggers"] = [{"effect": "ravenbloom", "owner": player}]
            if row["played"] == 2:
                item["post_triggers"].append({"effect": "darius", "owner": player})
            if state["turn_player"] != player:
                item["post_triggers"].extend(
                    {"effect": "viktor_innovator", "owner": player}
                    for source in self._units(state, player)
                    if source["code"] == "OGN-117"
                )
            # Keep a pending spell item while the player chooses its target;
            # target confirmation fills that item before normal chain resolution.
            self._enter_chain(state, [item])
            state["decision"] = {"kind": "target", "player": player,
                                  "targets": list(args.get("target_candidates", [])),
                                  "multi": code in (PAIR_TARGET_SPELLS | OPTIONAL_TARGET_SPELLS | CONSTRAINED_MULTI_TARGET_SPELLS | {"OGN-029", "OGN-105", "OGN-206", "OGN-248"}), "min": int(args.get("target_min", 1)),
                                  "max": int(args.get("target_max", 1)), "selected": [],
                                  "allow_repeat": bool(args.get("allow_repeat", False)),
                                  "target_pairs": [list(pair) for pair in (args.get("target_pairs") or [])
                                                   if pair is not None],
                                  "ordered_pairs": bool(args.get("ordered_pairs", False)),
                                  "destination_select": bool(args.get("destination_select", False)),
                                  "target_might_limit": args.get("target_might_limit"),
                                  "same_location": bool(args.get("same_location", False)),
                                  "item": item, "play_targeted": True,
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
            was_legion = row["played"] > 0
            if kind == "play_unit":
                ignore_cost = bool(args.get("ignore_cost"))
                additional_cost = bool(args.get("additional_cost"))
                sacrifice_id = args.get("sacrifice")
                discard_card = args.get("discard_card")
                spend_buffs = list(args.get("spend_buffs") or [])
                kill_units = list(args.get("kill_units") or [])
                energy = 0 if ignore_cost else max(0, data["energy"] - (2 if code == "OGN-012" and was_legion else 0)
                                                    - (2 if discard_card else 0)
                                                    + int(additional_cost))
                power_cost = max(0, data["power_cost"] - len(spend_buffs) - len(kill_units))
                self._pay(row, energy, [] if ignore_cost else args["payment"])
                if not ignore_cost and discard_card is not None:
                    if discard_card not in row["hand"] or discard_card == card:
                        raise ValueError("Brazen Buccaneer requires a different card to discard")
                    row["hand"].remove(discard_card)
                    row["trash"].append(discard_card)
                    row["discarded_this_turn"] = True
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
                    if killed.get("card") is not None:
                        row["trash"].append(killed["card"])
                if not ignore_cost and code == "OGN-208":
                    sacrificed = self._unit(state, sacrifice_id)
                    if sacrificed is None or sacrificed["owner"] != player:
                        raise ValueError("Cruel Patron requires a friendly unit sacrifice")
                    state["units"].remove(sacrificed)
                    if sacrificed.get("card") is not None:
                        row["trash"].append(sacrificed["card"])
                zone = row["hand"] if card in row["hand"] else row["champion"]
                zone.remove(card)
                ready = (any(u["code"] == "OGN-011" for u in self._units(state, player))
                         or row.get("ready_play", False))
                ready = ready or code == "OGN-159"
                if code == "OGN-035":
                    ready = ready or any(field["controller"] == 1-player for field in state["fields"])
                if code == "OGN-079":
                    ready = ready or state["victory"] - state["points"][1-player] <= 3
                unit = self._new_unit(state, code, player, args["location"], card=card, exhausted=not ready)
                if args.get("hidden_field") is not None:
                    unit["hidden_field"] = args["hidden_field"]
                row["played"] += 1
                if (row["legend"] == "OGN-249" and not row["legend_exhausted"]
                        and self.might(state, unit) >= 5):
                    state.setdefault("legend_options", []).append({"owner": player,
                                                                      "source": unit["id"]})
                triggers = self._second_card_triggers(state, player)
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
                if code in {"OGN-030", "OGN-086", "OGN-100", "OGN-171", "OGN-174"}:
                    triggers.append({"effect": "discard_two" if code == "OGN-030" else "vision",
                                     "source": unit["id"], "owner": player})
                elif any(other["code"] == "OGN-100" for other in self._units(state, player)):
                    triggers.append({"effect": "vision", "source": unit["id"], "owner": player})
                if code in ACCELERATE:
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
                            "domains": list(data["domains"]),
                            "triggers": copy.deepcopy(triggers),
                            "scrapyard_discard": code == "OGN-020" and was_legion,
                            "replay_optional": code in {"OGN-196", "OGN-226"},
                        },
                    }
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
                    return
                if code == "OGN-020" and was_legion and row["hand"]:
                    state["decision"] = {"kind": "discard", "player": player,
                                          "remaining": min(2, len(row["hand"])),
                                          "scrapyard_discard": True,
                                          "post_triggers": triggers}
                    state["phase"], state["actor"], state["passes"] = "decision", player, 0
                    return
                if code == "OGN-020" and was_legion:
                    self._draw(state, player, 2, rng)
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
                spell_energy = 0 if spend is not None or ignore_cost else max(0, data["energy"] - row.get("spell_discount", 0))
                self._pay(row, spell_energy,
                          [] if ignore_cost else args["payment"])
                if spend is None and not ignore_cost:
                    row["spell_discount"] = 0
                if spend is not None:
                    self._unit(state, spend)["buff"] = 0
                row["hand"].remove(card)
                row["played"] += 1
                effect = "return_unit" if code == "OGN-170" else ("sabotage" if code == "OGN-156" else "spell")
                triggers = self._second_card_triggers(state, player)
                spell_item = {"effect": effect, "owner": player, "card": card,
                               "code": code, "targets": args["targets"],
                               "destination": args.get("destination"),
                               "x": args.get("x", 0),
                               "legion": was_legion}
                if code in SPELL_CODES:
                    spell_item["post_triggers"] = [{"effect": "ravenbloom", "owner": player}]
                    if row["played"] == 2:
                        spell_item["post_triggers"].append({"effect": "darius", "owner": player})
                    if state["turn_player"] != player:
                        spell_item["post_triggers"].extend(
                            {"effect": "viktor_innovator", "owner": player}
                            for source in self._units(state, player)
                            if source["code"] == "OGN-117"
                        )
                    # Playing a spell completes only after its resolution, so
                    # Darius's second-card trigger is a post-spell trigger too.
                    triggers = []
                self._enter_chain(state, [spell_item])
                self._cleanup(state, rng)
                self._triggers(state, triggers)
        elif kind == "order_triggers":
            pending = state["pending"]
            state["pending"] = []
            state["phase"] = state["order_return"]
            preserve_context = state.pop("preserve_chain_context", False)
            self._enter_chain(state, [pending[i] for i in args["order"]],
                              preserve_context=preserve_context)
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
            for unit in self._units(state, player):
                if unit["code"] == "OGN-073" and self._is_field(state, unit["location"]):
                    for rune in state["players"][player]["runes"][:4]:
                        rune["exhausted"] = False
            for unit in state["units"]:
                unit["damage"], unit["temporary"], unit["assault"], unit["stunned"] = 0, 0, 0, False
                unit["temporary_tank"] = False
                unit["kill_on_damage"] = None
            for obj in state["players"]:
                obj["energy"], obj["power"] = 0, []
            state["prevent_spell_ability_damage"] = False
            decree = state.get("imperial_decree")
            if decree and decree.get("turn") == state.get("turn"):
                state.pop("imperial_decree", None)
            self._cleanup(state, rng)
            state["turn_player"] = 1-player
            if state["winner"] is None:
                self._start_turn(state, rng)
        else:
            raise ValueError(f"unknown action {kind}")

    def _resolve_chain_item(self, state, rng):
        item = state["chain"].pop()
        completed = self.effects.dispatch(item["effect"], state, item, rng)
        if completed:
            # Ravenbloom Student and other post-spell triggers are created only
            # after the spell has finished resolving.  Keeping them on the
            # spell item prevents them from incorrectly resolving before it.
            post_triggers = item.pop("post_triggers", None)
            if post_triggers:
                generated = []
                for spec in post_triggers:
                    if spec.get("effect") == "ravenbloom":
                        generated.extend(
                            {"effect": "ravenbloom", "source": source["id"],
                             "owner": item["owner"]}
                            for source in self._units(state, item["owner"])
                            if source["code"] == "OGN-103"
                        )
                    elif spec.get("effect") == "darius":
                        generated.extend(
                            {"effect": "darius", "source": source["id"],
                             "owner": item["owner"]}
                            for source in self._units(state, item["owner"])
                            if source["code"] == "OGN-027"
                        )
                    elif spec.get("effect") == "viktor_innovator":
                        generated.extend(
                            {"effect": "viktor_innovator", "source": source["id"],
                             "owner": item["owner"]}
                            for source in self._units(state, item["owner"])
                            if source["code"] == "OGN-117"
                        )
                if generated:
                    if len(generated) == 1:
                        state["chain"].extend(generated)
                        state["phase"], state["actor"], state["passes"] = "chain", generated[0]["owner"], 0
                        self._arm_chain_top(state)
                    else:
                        state["pending"] = generated
                        state["order_return"] = "chain"
                        state["preserve_chain_context"] = True
                        state["phase"], state["actor"] = "trigger_order", generated[0]["owner"]
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
            else:
                state["actor"] = state["turn_player"]

    def _open_combat_trigger_target(self, state):
        """Finalize designation triggers one at a time before adding them to chain."""
        queue = state.setdefault("combat_trigger_queue", [])
        while queue:
            item = queue.pop(0)
            field = state["battle"]["field"]
            targets = [unit["id"] for unit in self._units(state, 1 - item["owner"], field)]
            if not targets:
                continue
            state["decision"] = {
                "kind": "target", "player": item["owner"], "targets": targets,
                "item": item, "resume": "combat_trigger",
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
                for unit in attackers if unit["code"] == "OGN-119"
            ] + [
                {"effect": "ahri_debuff", "source": unit["id"],
                 "owner": unit["owner"], "role": "defender"}
                for unit in defenders if unit["code"] == "OGN-119"
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
                    self._unit(state, uid)["damage"] += amount
            self._settle_battle(state, rng)

    def _settle_battle(self, state, rng):
        battle = state["battle"]
        field, attacker = battle["field"], battle["attacker"]
        self._cleanup(state, rng)  # Kill lethal before healing, with combat modifiers active.
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
        if (controller == attacker and battle.get("excess", [0, 0])[attacker] >= 5
                and any(unit["code"] == "OGN-034" and unit["owner"] == attacker
                        and unit["location"] == field for unit in state["units"])):
            state["points"][attacker] += 1
        state["battle"], state["phase"], state["actor"] = None, "main", state["turn_player"]
        if controller is not None and controller != previous:
            self._score(state, controller, field, "conquer", rng)
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
                                   "trash": [card(uid) for uid in row["trash"]], "played": row["played"]})
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
                        or state["cards"][gear["card"]]["owner"] != player
                        or gear.get("exhausted") not in (True, False)):
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
        if state["decision"] and state["decision"].get("kind") == "target":
            item = state["decision"].get("item", {})
            # A multi-target spell remains on the chain while its target window
            # is open; count its physical card only once.
            chain_cards = {entry.get("card") for entry in state["chain"]}
            if item.get("card") is not None and item["card"] not in chain_cards:
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
