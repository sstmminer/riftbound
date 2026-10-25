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
from .core import Card, Deck, Scoreboard, Unit, channel_count, draw_cards, mulligan, validate_deck
from .engine import Action, canonical
from .support import ACCELERATE, FIELD_CODES, LEGEND, REACTIONS, RUNES, SPELL_CODES, TOKEN, UNIT_CODES, starter_deck


def card_model(row):
    return Card(row["code"], row["name"], row["type"], frozenset(row["domains"]),
                frozenset(row["tags"]), row["champion"], row["signature"],
                rules_text=row["text"])


class OriginsRules:
    def __init__(self, decks=None):
        self.cards = {row["code"]: row for row in load_origins()}
        self.decks = copy.deepcopy(decks if decks is not None else [starter_deck(), starter_deck()])
        if len(self.decks) != 2:
            raise ValueError("exactly two decks required")
        models = {code: card_model(row) for code, row in self.cards.items()}
        for deck in self.decks:
            validate_deck(Deck(deck["legend"], deck["chosen_champion"], tuple(deck["main"]),
                               tuple(deck["runes"]), tuple(deck["battlefields"])), models)
            require_supported(tuple([deck["legend"], *deck["main"], *deck["runes"], *deck["battlefields"]]))
            if deck["legend"] != LEGEND or not set(deck["runes"]) <= RUNES or not set(deck["battlefields"]) <= FIELD_CODES:
                raise ValueError("deck contains unsupported legend, rune or battlefield")
            if any(self.cards[code]["token"] for code in deck["main"]):
                raise ValueError("tokens cannot be included in a constructed main deck")
        digest = hashlib.sha256(canonical({"cards": list(self.cards.values()), "decks": self.decks}).encode()).hexdigest()
        self.id = f"origins-subset/0.2.0/RUP5-2026-10-09/{digest}"

    def initial_state(self, rng):
        first = rng.randrange(2)
        state = {"first": first, "turn_player": first, "actor": first, "turn": 0,
                 "phase": "mulligan", "mulligans": 0, "players": [], "cards": {},
                 "units": [], "fields": [], "points": [0, 0], "scored": [[], []],
                 "chain": [], "pending": [], "passes": 0, "battle": None,
                 "selection": None, "winner": None, "next_object": 0}
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
                                     "trash": [], "rune_deck": runes, "runes": [], "energy": 0,
                                     "power": [], "legend": deck["legend"], "legend_exhausted": False,
                                     "turns": 0, "played": 0})
            state["fields"].append({"code": rng.choice(deck["battlefields"]), "controller": None})
        state["victory"] = 8 + sum(f["code"] == "OGN-276" for f in state["fields"])
        return state

    def player(self, state):
        return state["actor"]

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
        if location in (0, 1) and state["fields"][location]["code"] == "OGN-294":
            value += 1
        role = self._role(state, unit)
        if role == "attacker":
            value += int(unit["code"] in {"OGN-210", "OGN-215"}) + unit["assault"]
            value += sum(other["code"] == "OGN-015" and other["id"] != unit["id"]
                         for other in self._units(state, unit["owner"], location))
        if role == "defender" and unit["code"] == "OGN-232" and value >= 5:
            value += 1
        return value

    def _deflect(self, state, unit):
        return int(unit["code"] == "OGN-013" or
                   (unit["code"] == "OGN-232" and self.might(state, unit) >= 5))

    def _ganking(self, state, unit):
        location = unit["location"]
        return ((unit["code"] == "OGN-232" and self.might(state, unit) >= 5)
                or (location in (0, 1) and state["fields"][location]["code"] == "OGN-297"))

    def _cleanup(self, state):
        for player in (0, 1):
            if state["points"][player] >= state["victory"] and state["points"][player] > state["points"][1-player]:
                state["winner"] = player
                return
        while True:
            dead = [u for u in state["units"] if u["damage"] > 0 and u["damage"] >= self.might(state, u)]
            if not dead:
                break
            for unit in dead:
                state["units"].remove(unit)
                if unit["card"] is not None:
                    state["players"][unit["owner"]]["trash"].append(unit["card"])
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
        board = Scoreboard(state["points"], [set(s) for s in state["scored"]], state["victory"], 2)
        result = board.score(player, field, method=method)
        state["scored"] = [sorted(s) for s in board.scored]
        if result == "draw":
            self._draw(state, player, 1, rng)
        self._cleanup(state)

    def _start_turn(self, state, rng):
        state["turn"] += 1
        player = state["turn_player"]
        state["actor"], state["phase"] = player, "main"
        state["scored"] = [[], []]
        for row in state["players"]:
            row["played"] = 0
        row = state["players"][player]
        row["legend_exhausted"] = False
        for rune in row["runes"]:
            rune["exhausted"] = False
        for unit in self._units(state, player):
            unit["exhausted"] = False
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
        self._cleanup(state)

    def _resource_actions(self, state):
        player = state["actor"]
        row = state["players"][player]
        result = []
        for rune in row["runes"]:
            if not rune["exhausted"]:
                result.append(Action.make("exhaust_rune", rune=rune["id"]))
            result.append(Action.make("recycle_rune", rune=rune["id"]))
        if not row["legend_exhausted"] and row["played"]:
            result.append(Action.make("legend_energy"))
        return result

    def _payments(self, state, player, energy, domains, power_count, any_count=0):
        row = state["players"][player]
        if row["energy"] < energy:
            return []
        result = []
        for chosen in combinations(range(len(row["power"])), power_count+any_count):
            # All colored costs of supported spells use the same card domain.
            if sum(row["power"][i] in domains or row["power"][i] == "any" for i in chosen) >= power_count:
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
            if code == "OGN-206":
                targets = [list(pair) for pair in combinations([u["id"] for u in self._units(state, player)], 2)]
            else:
                targets = [[u["id"]] for u in state["units"]
                           if code not in {"OGN-009", "OGN-024"} or u["location"] in (0, 1)]
            buffs = [None]
            if code == "OGN-207":
                buffs += [u["id"] for u in self._units(state, player) if u["buff"]]
            for selected in targets:
                deflect = sum(self._deflect(state, self._unit(state, uid)) for uid in selected
                              if self._unit(state, uid)["owner"] != player)
                for spend in buffs:
                    energy = 0 if spend is not None else data["energy"]
                    power = 0 if spend is not None else data["power_cost"]
                    for payment in self._payments(state, player, energy, data["domains"], power, deflect):
                        result.append(Action.make("play_spell", card=card, targets=selected,
                                                  spend_buff=spend, payment=payment))
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
            energy = data["energy"] - (2 if code == "OGN-012" and row["played"] else 0)
            for accelerate in ([False, True] if code in ACCELERATE else [False]):
                for payment in self._payments(state, player, energy+int(accelerate), data["domains"],
                                               data["power_cost"]+int(accelerate)):
                    for location in locations:
                        result.append(Action.make("play_unit", card=card, location=location,
                                                  accelerate=accelerate, payment=payment))
        return result

    def _movable(self, state, destination):
        player = state["actor"]
        base = f"base:{player}"
        return [u["id"] for u in self._units(state, player) if not u["exhausted"]
                and u["location"] != destination
                and ((destination == base and u["location"] in (0, 1))
                     or (destination in (0, 1) and (u["location"] == base or self._ganking(state, u))))]

    def legal_actions(self, state):
        if state["winner"] is not None:
            return ()
        phase, player = state["phase"], state["actor"]
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
            return tuple(Action.make("assign_damage", target=u["id"]) for u in (unassigned or targets))
        result = self._resource_actions(state) + self._spell_actions(state)
        if phase in {"chain", "showdown"}:
            result.append(Action.make("pass"))
        elif phase == "main":
            result.extend(self._unit_actions(state))
            for destination in (f"base:{player}", 0, 1):
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
                "temporary": 0, "assault": 0, "damage": 0}
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

    def apply(self, state, action, rng):
        kind, args = action.kind, json.loads(action.arguments)
        player = state["actor"]
        row = state["players"][player]
        if kind == "mulligan":
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
                ready = args["accelerate"] or any(u["code"] == "OGN-011" for u in self._units(state, player))
                unit = self._new_unit(state, code, player, args["location"], card=card, exhausted=not ready)
                row["played"] += 1
                triggers = self._second_card_triggers(state, player)
                if code == "OGN-217" and was_legion:
                    triggers.append({"effect": "buff_self", "source": unit["id"], "owner": player})
                if code == "OGN-223":
                    triggers.append({"effect": "peak", "source": unit["id"], "owner": player})
                self._cleanup(state)
                self._triggers(state, triggers)
            else:
                spend = args["spend_buff"]
                self._pay(row, 0 if spend is not None else data["energy"], args["payment"])
                if spend is not None:
                    self._unit(state, spend)["buff"] = 0
                row["hand"].remove(card)
                row["played"] += 1
                self._enter_chain(state, [{"effect": "spell", "owner": player, "card": card,
                                           "code": code, "targets": args["targets"]}])
                self._cleanup(state)
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
            for unit in moved:
                unit["location"], unit["exhausted"] = destination, True
            state["selection"], state["phase"] = None, "main"
            self._cleanup(state)
            if destination in (0, 1) and state["fields"][destination]["controller"] != player:
                state["battle"] = {"field": destination, "attacker": player,
                                   "combat": bool(self._units(state, 1-player, destination))}
                state["phase"], state["focus"], state["passes"] = "showdown", player, 0
            self._triggers(state, [{"effect": "drummer", "owner": player, "location": destination}
                                   for unit in moved if unit["code"] == "OGN-222" and destination in (0, 1)])
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
            self._cleanup(state)
            for unit in state["units"]:
                unit["damage"], unit["temporary"], unit["assault"] = 0, 0, 0
            for obj in state["players"]:
                obj["energy"], obj["power"] = 0, []
            self._cleanup(state)
            state["turn_player"] = 1-player
            if state["winner"] is None:
                self._start_turn(state, rng)
        else:
            raise ValueError(f"unknown action {kind}")

    def _resolve_chain_item(self, state, rng):
        item = state["chain"].pop()
        effect, owner = item["effect"], item["owner"]
        source = self._unit(state, item.get("source"))
        if effect == "darius" and source:
            source["temporary"] += 2
            source["exhausted"] = False
        elif effect in {"buff_self", "peak"} and source:
            source["buff"] = 1
            if effect == "peak" and source["location"] in (0, 1):
                for unit in self._units(state, owner, source["location"]):
                    unit["buff"] = 1
        elif effect == "drummer":
            self._new_unit(state, TOKEN, owner, item["location"])
        elif effect == "spell":
            code = item["code"]
            for uid in item["targets"]:
                unit = self._unit(state, uid)
                if unit is None or (code in {"OGN-009", "OGN-024"} and unit["location"] not in (0, 1)):
                    continue
                if code in {"OGN-206", "OGN-207"}:
                    unit["temporary"] += 2 if code == "OGN-206" else 3
                elif code == "OGN-004":
                    unit["assault"] += 3
                elif code in {"OGN-009", "OGN-024"}:
                    unit["damage"] += 3 if code == "OGN-009" else 4
            self._cleanup(state)
            if code == "OGN-024" and state["winner"] is None:
                self._draw(state, owner, 1, rng)
            state["players"][owner]["trash"].append(item["card"])
        if state["chain"]:
            state["actor"] = state["chain"][-1]["owner"]
        else:
            state["phase"] = state["chain_return"]
            if state["phase"] == "showdown":
                if state["chain_from_spell"]:
                    state["focus"] = 1-state["focus"]
                state["actor"] = state["focus"]
            else:
                state["actor"] = state["turn_player"]
        self._cleanup(state)

    def _close_showdown(self, state, rng):
        battle = state["battle"]
        field = battle["field"]
        if not battle["combat"] or not self._units(state, 0, field) or not self._units(state, 1, field):
            self._settle_battle(state, rng)
            return
        battle["damage"] = {"remaining": [sum(max(0, self.might(state, u)) for u in self._units(state, p, field))
                                           for p in (0, 1)], "assignments": [{}, {}]}
        state["phase"], state["actor"] = "damage", battle["attacker"]
        self._advance_damage(state, rng)

    def _assign_damage(self, state, target_id, rng):
        player = state["actor"]
        damage = state["battle"]["damage"]
        targets = self._units(state, 1-player, state["battle"]["field"])
        assignments = damage["assignments"][player]
        unit = self._unit(state, target_id)
        if all(u["id"] in assignments for u in targets):
            amount = damage["remaining"][player]
        else:
            amount = min(damage["remaining"][player], max(1, self.might(state, unit))-unit["damage"])
        assignments[target_id] = assignments.get(target_id, 0) + amount
        damage["remaining"][player] -= amount
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
        self._cleanup(state)  # Kill lethal before healing, with combat modifiers active.
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
        self._cleanup(state)

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
                                   "trash": [card(uid) for uid in row["trash"]], "played": row["played"]})
        return {"player": player, "to_act": state["actor"], "turn_player": state["turn_player"],
                "turn": state["turn"], "phase": state["phase"], "points": state["points"].copy(),
                "victory": state["victory"], "hand": [card(uid) for uid in state["players"][player]["hand"]],
                "players": public_players, "fields": copy.deepcopy(state["fields"]),
                "units": [{**copy.deepcopy(u), "might": self.might(state, u)} for u in state["units"]],
                "chain": copy.deepcopy(state["chain"]), "pending": copy.deepcopy(state["pending"]),
                "battle": copy.deepcopy(state["battle"]),
                "selection": copy.deepcopy(state["selection"]) if player == state["actor"] else None,
                "winner": state["winner"]}

    def validate(self, state):
        if state["actor"] not in (0, 1) or state["turn_player"] not in (0, 1):
            raise ValueError("invalid actor")
        located = []
        for player, row in enumerate(state["players"]):
            for zone in ("main", "hand", "champion", "trash"):
                located.extend(row[zone])
                if any(state["cards"][uid]["owner"] != player for uid in row[zone]):
                    raise ValueError("card in non-owner zone")
            runes = row["runes"] + row["rune_deck"]
            if len(runes) != 12 or len({r["id"] for r in runes}) != 12:
                raise ValueError("rune conservation failed")
            if row["energy"] < 0 or any(p not in {"fury", "order"} for p in row["power"]):
                raise ValueError("invalid resource pool")
        located.extend(u["card"] for u in state["units"] if u["card"] is not None)
        located.extend(item["card"] for item in state["chain"] if item["effect"] == "spell")
        if Counter(located) != Counter(state["cards"].keys()):
            raise ValueError("main-deck card conservation failed")
        if len({u["id"] for u in state["units"]}) != len(state["units"]):
            raise ValueError("duplicate object IDs")
        for unit in state["units"]:
            if unit["location"] not in (0, 1, f"base:{unit['owner']}") or unit["damage"] < 0 or unit["buff"] not in (0, 1):
                raise ValueError("invalid unit state")
        if state["phase"] == "main":
            for field, obj in enumerate(state["fields"]):
                occupants = {u["owner"] for u in self._units(state, location=field)}
                if len(occupants) > 1:
                    raise ValueError("unresolved combat in neutral state")
                if obj["controller"] is not None and obj["controller"] not in occupants:
                    raise ValueError("controller without units")
