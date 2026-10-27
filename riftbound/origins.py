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
from .support import ACCELERATE, FIELD_CODES, LEGENDS, REACTIONS, RUNES, SPELL_CODES, TOKEN, UNIT_CODES, starter_deck


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
        registry.register("draw_one", self._effect_draw_one)
        registry.register("channel_one", self._effect_channel_one)
        registry.register("return_unit", self._effect_return_unit)
        registry.register("spell", self._effect_spell)
        return registry

    def initial_state(self, rng):
        first = rng.randrange(2)
        state = {"first": first, "turn_player": first, "actor": first, "turn": 0,
                 "phase": "mulligan", "mulligans": 0, "players": [], "cards": {},
                 "units": [], "fields": [], "points": [0, 0], "scored": [[], []],
                 "chain": [], "pending": [], "passes": 0, "battle": None,
                 "beginning_awarded": [False, False], "selection": None,
                 "decision": None, "legend_options": [], "winner": None, "next_object": 0}
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
                                     "trash": [], "banishment": [], "rune_deck": runes, "runes": [], "energy": 0,
                                     "power": [], "buff_bonus": 0, "legend": deck["legend"], "legend_exhausted": False,
                                     "turns": 0, "played": 0, "ready_play": False})
            state["fields"].append({"code": rng.choice(deck["battlefields"]), "controller": None})
        state["fields"].extend({"code": code, "controller": None} for code in self.extra_fields)
        state["victory"] = 8 + sum(f["code"] == "OGN-276" for f in state["fields"])
        return state

    def player(self, state):
        return state["actor"]

    def _is_field(self, state, location):
        return type(location) is int and 0 <= location < len(state["fields"])

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
        if role == "defender" and unit["code"] == "OGN-054":
            value += 1
        if role == "defender" and unit["code"] == "OGN-238":
            value += 1
        if role == "defender" and unit["code"] == "OGN-241":
            value += 2
        if role == "attacker":
            value += int(unit["code"] in {"OGN-210", "OGN-215"}) + unit["assault"]
            value += 3 if unit["code"] == "OGN-035" else 0
            value += 2 if unit["code"] in {"OGN-003", "OGN-030"} else 0
            if unit["code"] == "OGN-131" and any(not other["exhausted"]
                                                    for other in self._units(state, 1-unit["owner"], location)):
                value += 2
            value += sum(other["code"] == "OGN-015" and other["id"] != unit["id"]
                         for other in self._units(state, unit["owner"], location))
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
        if self._is_field(state, unit["location"]) and state["fields"][unit["location"]]["code"] == "OGN-296":
            amount += 1
        unit["damage"] += amount

    def _deflect(self, state, unit):
        return int(unit["code"] == "OGN-013" or
                   (unit["code"] == "OGN-232" and self.might(state, unit) >= 5))

    def _ganking(self, state, unit):
        location = unit["location"]
        return ((unit["code"] == "OGN-232" and self.might(state, unit) >= 5)
                or (self._is_field(state, location) and state["fields"][location]["code"] == "OGN-297"))

    def _tank(self, unit):
        return unit["code"] in {"OGN-054", "OGN-087", "OGN-137", "OGN-241"}

    def _cleanup(self, state, rng=None):
        for player in (0, 1):
            if state["points"][player] >= state["victory"] and state["points"][player] > state["points"][1-player]:
                state["winner"] = player
                return
        deathknell = []
        deathknell_channel = []
        while True:
            dead = [u for u in state["units"] if u["damage"] > 0 and u["damage"] >= self.might(state, u)]
            if not dead:
                break
            for unit in dead:
                state["units"].remove(unit)
                if unit["card"] is not None:
                    state["players"][unit["owner"]]["trash"].append(unit["card"])
                if unit["code"] == "OGN-096":
                    deathknell.append(unit["owner"])
                if unit["code"] == "OGN-216":
                    deathknell_channel.append(unit["owner"])
        if deathknell:
            draw_rng = rng if rng is not None else random.Random(0)
            for player in deathknell:
                self._draw(state, player, 1, draw_rng)
        for player in deathknell_channel:
            self._channel_rune(state, player, exhausted=True)
        if state["phase"] == "main":
            for field, row in enumerate(state["fields"]):
                if row["controller"] is not None and not self._units(state, row["controller"], field):
                    row["controller"] = None

    def _draw(self, state, player, count, rng):
        row = state["players"][player]
        result = draw_cards(tuple(row["main"]), tuple(row["trash"]), count, player=player,
                            points=tuple(state["points"]), rng=rng, victory=state["victory"])
        row["main"], row["trash"] = list(result.main), list(result.trash)
        row["hand"].extend(result.drawn)
        state["points"] = list(result.points)
        if result.immediate_winner is not None:
            state["winner"] = result.immediate_winner

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
            elif code == "OGN-288":  # Startipped Peak
                row = state["players"][player]
                if row["rune_deck"]:
                    rune = {**row["rune_deck"].pop(0), "exhausted": True}
                    row["runes"].append(rune)
        if result in {"point", "draw"} and method == "conquer":
            if state["fields"][field]["code"] == "OGN-298":  # Zaun Warrens
                row = state["players"][player]
                if row["hand"]:
                    row["trash"].append(row["hand"].pop(0))
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
        for row in state["players"]:
            row["played"] = 0
            row["ready_play"] = False
            row["buff_bonus"] = 0
        row = state["players"][player]
        row["legend_exhausted"] = False
        if row["turns"] == 0 and not state["beginning_awarded"][player]:
            state["points"][player] += sum(field["code"] == "OGN-290"
                                            for field in state["fields"])
            state["beginning_awarded"][player] = True
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
        count = channel_count(first_turn=row["turns"] == 0, second_player=player != state["first"],
                              available=len(row["rune_deck"]))
        row["runes"].extend(row["rune_deck"][:count])
        del row["rune_deck"][:count]
        row["turns"] += 1
        self._draw(state, player, 1, rng)
        # 316.3: both pools empty at the start of Main Phase, after Draw.
        for obj in state["players"]:
            obj["energy"], obj["power"] = 0, []
        self._cleanup(state, rng)

    def _resource_actions(self, state):
        player = state["actor"]
        row = state["players"][player]
        result = []
        for rune in row["runes"]:
            if not rune["exhausted"]:
                result.append(Action.make("exhaust_rune", rune=rune["id"]))
            result.append(Action.make("recycle_rune", rune=rune["id"]))
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
        for card in row["hand"]:
            code = state["cards"][card]["code"]
            if code not in SPELL_CODES or (state["phase"] == "chain" and code not in REACTIONS):
                continue
            data = self.cards[code]
            if code in {"OGN-047", "OGN-083", "OGN-114", "OGN-127", "OGN-129", "OGN-133", "OGN-134", "OGN-170", "OGN-201", "OGN-233"}:
                targets = [[]]
            elif code == "OGN-043":
                targets = [[u["id"]] for u in self._units(state, 1-player)]
            elif code == "OGN-173":
                targets = [[u["id"]] for u in self._units(state, player)]
            elif code in {"OGN-053", "OGN-069", "OGN-104"}:
                targets = [[u["id"]] for u in self._units(state, player)]
            elif code in {"OGN-169", "OGN-172", "OGN-213"}:
                targets = [[u["id"]] for u in state["units"] if self._is_field(state, u["location"])
                           and (code != "OGN-169" or self.might(state, u) <= 3)]
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
            buffs = [None]
            if code == "OGN-207":
                buffs += [u["id"] for u in self._units(state, player) if u["buff"]]
            for selected in targets:
                destinations = [None]
                if code in {"OGN-043", "OGN-173"}:
                    unit = self._unit(state, selected[0])
                    destinations = [f"base:{unit['owner']}", *range(len(state["fields"]))]
                    destinations = [destination for destination in destinations
                                    if destination != unit["location"]]
                deflect = sum(self._deflect(state, self._unit(state, uid)) for uid in selected
                              if self._unit(state, uid)["owner"] != player)
                for destination in destinations:
                    for spend in buffs:
                        energy = 0 if spend is not None else data["energy"]
                        if code == "OGN-014" and spend is None:
                            highest = max((self.might(state, u) for u in self._units(state, player)), default=0)
                            energy = max(0, energy - highest)
                        if code == "OGN-047" and spend is None:
                            if state["victory"] - state["points"][1-player] <= 3:
                                energy = max(0, energy - 2)
                        power = 0 if spend is not None else data["power_cost"]
                        for payment in self._payments(state, player, energy, data["domains"], power, deflect,
                                                      spell=True):
                            result.append(Action.make("play_spell", card=card, targets=selected,
                                                      destination=destination, spend_buff=spend, payment=payment))
        return result

    def _unit_actions(self, state):
        player = state["actor"]
        row = state["players"][player]
        result = []
        locations = [f"base:{player}"] + [i for i, f in enumerate(state["fields"]) if f["controller"] == player]
        for card in row["hand"] + row["champion"]:
            code = state["cards"][card]["code"]
            if code not in UNIT_CODES:
                continue
            data = self.cards[code]
            permitted = locations.copy()
            if code == "OGN-176":
                permitted += [i for i in range(len(state["fields"])) if not self._units(state, location=i) and i not in permitted]
            energy = data["energy"] - (2 if code == "OGN-012" and row["played"] else 0)
            for accelerate in ([False, True] if code in ACCELERATE else [False]):
                for payment in self._payments(state, player, energy+int(accelerate), data["domains"],
                                               data["power_cost"]+int(accelerate)):
                    for location in permitted:
                        result.append(Action.make("play_unit", card=card, location=location,
                                                  accelerate=accelerate, payment=payment,
                                                  enter_target=None))
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

    def legal_actions(self, state):
        if state["winner"] is not None:
            return ()
        phase, player = state["phase"], state["actor"]
        if phase == "decision":
            if state["decision"]["kind"] == "predict":
                return (Action.make("predict", recycle=False), Action.make("predict", recycle=True))
            if state["decision"]["kind"] == "target":
                return tuple(Action.make("choose_target", target=uid)
                             for uid in state["decision"]["targets"])
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
            tanks = [u for u in unassigned if self._tank(u)]
            choices = tanks or unassigned or targets
            return tuple(Action.make("assign_damage", target=u["id"]) for u in choices)
        result = self._resource_actions(state) + self._spell_actions(state)
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

    def _enter_chain(self, state, items):
        if not state["chain"]:
            state["chain_return"] = state["phase"]
            state["chain_from_spell"] = any(item["effect"] == "spell" for item in items)
        state["chain"].extend(items)
        state["phase"], state["actor"], state["passes"] = "chain", items[-1]["owner"], 0

    def _triggers(self, state, triggers):
        if not triggers:
            return
        if len(triggers) == 1:
            self._enter_chain(state, triggers)
        else:
            state["pending"] = triggers
            state["order_return"] = state["phase"]
            state["phase"], state["actor"] = "trigger_order", triggers[0]["owner"]

    def _new_unit(self, state, code, owner, location, *, card=None, exhausted=None):
        if exhausted is None:
            exhausted = not any(u["code"] == "OGN-011" for u in self._units(state, owner))
        unit = {"id": self._object(state), "card": card, "code": code, "owner": owner,
                "location": location, "exhausted": exhausted, "buff": 0,
                "temporary": 0, "temporary_unit": False, "assault": 0,
                "damage": 0, "stunned": False}
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
        if hand:
            state["decision"] = {"kind": "discard", "player": owner,
                                  "remaining": min(2, len(hand))}
            state["phase"], state["actor"] = "decision", owner
            return False
        return True

    def _effect_discard_one(self, state, item, rng):
        owner = item["owner"]
        hand = state["players"][owner]["hand"]
        if hand:
            state["decision"] = {"kind": "discard", "player": owner, "remaining": 1}
            state["phase"], state["actor"] = "decision", owner
            return False
        return True

    def _open_target_choice(self, state, item, targets):
        """Pause a chain item until its controller chooses one legal target."""
        target_ids = [u["id"] if isinstance(u, dict) else u for u in targets]
        if not target_ids:
            return True
        state["decision"] = {"kind": "target", "player": item["owner"],
                              "targets": target_ids, "item": item}
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

    def _effect_draw_one(self, state, item, rng):
        self._draw(state, item["owner"], 1, rng)
        return True

    def _effect_channel_one(self, state, item, rng):
        self._channel_rune(state, item["owner"], exhausted=True)
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
        for uid in item["targets"]:
            unit = self._unit(state, uid)
            if unit is None or (code in {"OGN-005", "OGN-009", "OGN-014", "OGN-024", "OGN-085", "OGN-105"}
                                and not self._is_field(state, unit["location"])):
                continue
            if code in {"OGN-043", "OGN-173"}:
                destination = item.get("destination")
                valid_destination = (destination == f"base:{unit['owner']}" or
                                     self._is_field(state, destination))
                valid_owner = ((code == "OGN-043" and unit["owner"] != owner) or
                               (code == "OGN-173" and unit["owner"] == owner))
                if valid_destination and valid_owner and destination != unit["location"]:
                    origin = unit["location"]
                    unit["location"] = destination
                    unit["exhausted"] = code == "OGN-043"
                    if (self._is_field(state, origin)
                            and state["fields"][origin]["code"] == "OGN-277"):
                        unit["temporary"] += 1
            elif code == "OGN-053":
                state["players"][owner]["buff_bonus"] = 1
                self._apply_buff(state, unit)
            elif code == "OGN-069":
                # Last Stand doubles the unit's current Might for this turn;
                # the temporary marker is removed at the next Beginning Phase.
                unit["temporary"] += self.might(state, unit)
                unit["temporary_unit"] = True
            elif code in {"OGN-206", "OGN-207"}:
                unit["temporary"] += 2 if code == "OGN-206" else 3
            elif code == "OGN-004":
                unit["assault"] += 3
            elif code == "OGN-014":
                self._deal_damage(state, unit, 5)
            elif code in {"OGN-005", "OGN-009", "OGN-024", "OGN-029", "OGN-085"}:
                self._deal_damage(state, unit, {"OGN-005": 3, "OGN-009": 3, "OGN-024": 4,
                                                "OGN-029": 3, "OGN-085": 6}[code])
            elif code == "OGN-105":
                self._deal_damage(state, unit, 6)
            elif code == "OGN-229":
                unit["damage"] = max(unit["damage"], self.might(state, unit))
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
        if code == "OGN-047":
            self._draw(state, owner, 1, rng)
            self._channel_rune(state, owner)
        elif code == "OGN-134":
            if not self._channel_rune(state, owner, exhausted=True):
                self._draw(state, owner, 1, rng)
        elif code == "OGN-233":
            for unit in self._units(state, owner):
                unit["temporary"] += 5
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
                trash.extend(state["players"][player]["hand"])
                state["players"][player]["hand"] = []
                self._draw(state, player, 4, rng)
        elif code in {"OGN-024", "OGN-058", "OGN-095"} or (code == "OGN-005" and killed):
            if state["winner"] is None:
                self._draw(state, owner, 1, rng)
        state["players"][owner]["trash"].append(item["card"])
        return True

    def apply(self, state, action, rng):
        kind, args = action.kind, json.loads(action.arguments)
        player = state["actor"]
        row = state["players"][player]
        if kind in {"predict", "discard_card", "choose_target"}:
            if kind == "predict":
                if args["recycle"] and row["main"]:
                    row["main"].append(row["main"].pop(0))
                state["decision"] = None
            elif kind == "discard_card":
                row["hand"].remove(args["card"])
                row["trash"].append(args["card"])
                state["decision"]["remaining"] -= 1
                if not state["decision"]["remaining"] or not row["hand"]:
                    state["decision"] = None
            elif kind == "choose_target":
                decision = state["decision"]
                if args["target"] not in decision["targets"]:
                    raise ValueError("invalid target choice")
                item = dict(decision["item"])
                item["target"] = args["target"]
                state["decision"] = None
                self.effects.dispatch(item["effect"], state, item, rng)
            if state["decision"] is None:
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
            if kind == "exhaust_rune":
                rune["exhausted"] = True
                row["energy"] += 1
            else:
                row["runes"].remove(rune)
                row["power"].extend(self.cards[rune["code"]]["domains"])
                row["rune_deck"].append({**rune, "exhausted": False})
            state["passes"] = 0
        elif kind == "legend_energy":
            row["legend_exhausted"] = True
            row["energy"] += 1
            state["passes"] = 0
        elif kind == "legend_spell_power":
            row["legend_exhausted"] = True
            row["power"].append("spell_any")
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
        elif kind in {"play_unit", "play_spell"}:
            card = args["card"]
            code = state["cards"][card]["code"]
            data = self.cards[code]
            was_legion = row["played"] > 0
            if kind == "play_unit":
                energy = data["energy"] - (2 if code == "OGN-012" and was_legion else 0) + int(args["accelerate"])
                self._pay(row, energy, args["payment"])
                zone = row["hand"] if card in row["hand"] else row["champion"]
                zone.remove(card)
                ready = (args["accelerate"] or any(u["code"] == "OGN-011" for u in self._units(state, player))
                         or row.get("ready_play", False))
                ready = ready or code == "OGN-159"
                if code == "OGN-035":
                    ready = ready or any(field["controller"] == 1-player for field in state["fields"])
                unit = self._new_unit(state, code, player, args["location"], card=card, exhausted=not ready)
                row["played"] += 1
                if (row["legend"] == "OGN-249" and not row["legend_exhausted"]
                        and self.might(state, unit) >= 5):
                    state.setdefault("legend_options", []).append({"owner": player,
                                                                      "source": unit["id"]})
                triggers = self._second_card_triggers(state, player)
                if code == "OGN-217" and was_legion:
                    triggers.append({"effect": "buff_self", "source": unit["id"], "owner": player})
                if code == "OGN-003":
                    triggers.append({"effect": "discard_one", "source": unit["id"], "owner": player})
                if code == "OGN-234":
                    triggers.append({"effect": "kill_target", "source": unit["id"], "owner": player})
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
                if code == "OGN-211":
                    triggers.append({"effect": "drummer", "owner": player, "location": args["location"]})
                if code == "OGN-223":
                    triggers.append({"effect": "peak", "source": unit["id"], "owner": player})
                if code in {"OGN-030", "OGN-171"}:
                    triggers.append({"effect": "discard_two" if code == "OGN-030" else "vision",
                                     "source": unit["id"], "owner": player})
                self._cleanup(state, rng)
                if self._is_field(state, args["location"]) and state["fields"][args["location"]]["controller"] != player:
                    state["battle"] = {"field": args["location"], "attacker": player, "combat": False}
                    state["phase"], state["focus"], state["passes"] = "showdown", player, 0
                self._triggers(state, triggers)
            else:
                spend = args["spend_buff"]
                self._pay(row, 0 if spend is not None else data["energy"], args["payment"])
                if spend is not None:
                    self._unit(state, spend)["buff"] = 0
                row["hand"].remove(card)
                row["played"] += 1
                effect = "return_unit" if code == "OGN-170" else "spell"
                self._enter_chain(state, [{"effect": effect, "owner": player, "card": card,
                                           "code": code, "targets": args["targets"],
                                           "destination": args.get("destination")}])
                self._cleanup(state, rng)
                self._triggers(state, self._second_card_triggers(state, player))
        elif kind == "order_triggers":
            pending = state["pending"]
            state["pending"] = []
            state["phase"] = state["order_return"]
            self._enter_chain(state, [pending[i] for i in args["order"]])
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
            origins = {unit["id"]: unit["location"] for unit in moved}
            for unit in moved:
                unit["location"], unit["exhausted"] = destination, True
                if (self._is_field(state, origins[unit["id"]])
                        and state["fields"][origins[unit["id"]]]["code"] == "OGN-277"):
                    unit["temporary"] += 1
            state["selection"], state["phase"] = None, "main"
            self._cleanup(state, rng)
            if self._is_field(state, destination) and state["fields"][destination]["controller"] != player:
                state["battle"] = {"field": destination, "attacker": player,
                                   "combat": bool(self._units(state, 1-player, destination))}
                state["phase"], state["focus"], state["passes"] = "showdown", player, 0
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
            for unit in state["units"]:
                unit["damage"], unit["temporary"], unit["assault"], unit["stunned"] = 0, 0, 0, False
            for obj in state["players"]:
                obj["energy"], obj["power"] = 0, []
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
            self._finish_resolution(state)
            self._cleanup(state, rng)

    def _finish_resolution(self, state):
        if state["chain"]:
            state["phase"] = "chain"
            state["actor"] = state["chain"][-1]["owner"]
        else:
            state["phase"] = state["chain_return"]
            if state["phase"] == "showdown":
                if state["chain_from_spell"]:
                    state["focus"] = 1-state.get("focus", state["actor"])
                state["actor"] = state["focus"]
            else:
                state["actor"] = state["turn_player"]

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
        if any(unit["code"] == "OGN-148" for unit in attackers):
            for unit in defenders:
                self._deal_damage(state, unit, 3)
        for _ in range(sum(unit["code"] == "OGN-130" for unit in attackers)):
            if defenders:
                self._deal_damage(state, defenders[0], 1)
        if any(unit["code"] == "OGN-238" for unit in attackers) and defenders:
            defenders[0]["stunned"] = True
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
                                           for p in (0, 1)], "assignments": [{}, {}]}
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
            if not damage["remaining"][player]:
                break
            other_targets = [u for u in targets if u["id"] != target_id and u["id"] not in assignments]
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
        if battle["combat"]:
            for unit in state["units"]:
                unit["damage"] = 0
            if self._units(state, 1-attacker, field):
                for unit in self._units(state, attacker, field):
                    unit["location"] = f"base:{attacker}"
        occupants = {u["owner"] for u in self._units(state, location=field)}
        controller = next(iter(occupants)) if len(occupants) == 1 else None
        previous = state["fields"][field]["controller"]
        state["fields"][field]["controller"] = controller
        state["battle"], state["phase"], state["actor"] = None, "main", state["turn_player"]
        if controller is not None and controller != previous:
            self._score(state, controller, field, "conquer", rng)
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
        public_players = []
        for index, row in enumerate(state["players"]):
            public_players.append({"hand_count": len(row["hand"]), "main_count": len(row["main"]),
                                   "rune_deck_count": len(row["rune_deck"]), "runes": copy.deepcopy(row["runes"]),
                                   "energy": row["energy"], "power": row["power"].copy(),
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
                "battle": copy.deepcopy(state["battle"]),
                "selection": copy.deepcopy(state["selection"]) if player == state["actor"] else None,
                "decision": ({**copy.deepcopy(state["decision"]),
                              "cards": ([card(state["players"][player]["main"][0])]
                                        if state["decision"]["kind"] == "predict" else [])}
                             if state["decision"] and state["decision"]["player"] == player else None),
                "winner": state["winner"]}

    def validate(self, state):
        if state["actor"] not in (0, 1) or state["turn_player"] not in (0, 1):
            raise ValueError("invalid actor")
        located = []
        for player, row in enumerate(state["players"]):
            for zone in ("main", "hand", "champion", "trash", "banishment"):
                located.extend(row[zone])
                if any(state["cards"][uid]["owner"] != player for uid in row[zone]):
                    raise ValueError("card in non-owner zone")
            runes = row["runes"] + row["rune_deck"]
            if len(runes) != 12 or len({r["id"] for r in runes}) != 12:
                raise ValueError("rune conservation failed")
            if row["energy"] < 0 or any(p not in DOMAINS | {"spell_any"} for p in row["power"]):
                raise ValueError("invalid resource pool")
        located.extend(u["card"] for u in state["units"] if u["card"] is not None)
        located.extend(item["card"] for item in state["chain"]
                       if item["effect"] in {"spell", "return_unit"})
        if state["decision"] and state["decision"].get("kind") == "target":
            item = state["decision"].get("item", {})
            if item.get("card") is not None:
                located.append(item["card"])
        if Counter(located) != Counter(state["cards"].keys()):
            raise ValueError("main-deck card conservation failed")
        if len({u["id"] for u in state["units"]}) != len(state["units"]):
            raise ValueError("duplicate object IDs")
        for unit in state["units"]:
            if (not self._is_field(state, unit["location"]) and unit["location"] != f"base:{unit['owner']}") or unit["damage"] < 0 or unit["buff"] not in (0, 1) or type(unit.get("stunned")) is not bool:
                raise ValueError("invalid unit state")
        if state["phase"] == "main":
            for field, obj in enumerate(state["fields"]):
                occupants = {u["owner"] for u in self._units(state, location=field)}
                if len(occupants) > 1:
                    raise ValueError("unresolved combat in neutral state")
                if obj["controller"] is not None and obj["controller"] not in occupants:
                    raise ValueError("controller without units")
