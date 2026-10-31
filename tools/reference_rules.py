"""Small, independent reference model for Origins core rules.

This module deliberately does not import the production engine, card catalog,
or ability registry.  It models only rule primitives that many cards share:
movement, target legality, damage/death, control ownership, recycling, chain
priority, and optional-effect ordering.  Card-specific text belongs in golden
scenarios that drive these primitives.
"""
from __future__ import annotations

from copy import deepcopy


class ReferenceRuleError(ValueError):
    """A rule action is illegal in the reference model."""


class ReferenceRules:
    def initial_state(self) -> dict:
        return {
            "phase": "main", "actor": 0, "turn_player": 0, "turn": 1,
            "points": [0, 0],
            "players": [
                {"main": [], "hand": [], "trash": [], "energy": 0},
                {"main": [], "hand": [], "trash": [], "energy": 0},
            ],
            "fields": [{"controller": None}, {"controller": None}],
            "cards": {}, "units": {}, "chain": [], "optional": [],
            "passes": 0, "decision": None, "events": [],
        }

    def clone(self, state: dict) -> dict:
        return deepcopy(state)

    def _event(self, state: dict, kind: str, **payload) -> None:
        state["events"].append({"kind": kind, **payload})

    def add_card(self, state: dict, card_id: str, owner: int,
                 zone: str = "hand") -> None:
        if card_id in state["cards"]:
            raise ReferenceRuleError(f"duplicate card: {card_id}")
        if owner not in (0, 1):
            raise ReferenceRuleError("invalid card owner")
        state["cards"][card_id] = {"owner": owner}
        state["players"][owner][zone].append(card_id)

    def add_unit(self, state: dict, unit_id: str, *, owner: int,
                 card_owner: int | None = None, card: str | None = None,
                 location: int | str = "base:0", might: int = 1,
                 exhausted: bool = False) -> None:
        if unit_id in state["units"]:
            raise ReferenceRuleError(f"duplicate unit: {unit_id}")
        if owner not in (0, 1) or might < 0:
            raise ReferenceRuleError("invalid unit")
        if card_owner is None:
            card_owner = owner
        if card is not None and card not in state["cards"]:
            raise ReferenceRuleError(f"unknown physical card: {card}")
        state["units"][unit_id] = {
            "id": unit_id, "owner": owner, "card_owner": card_owner,
            "card": card, "location": location, "might": might,
            "damage": 0, "exhausted": bool(exhausted),
        }

    def _unit(self, state: dict, unit_id: str) -> dict:
        try:
            return state["units"][unit_id]
        except KeyError as exc:
            raise ReferenceRuleError(f"unknown unit: {unit_id}") from exc

    def legal_move_targets(self, state: dict, unit_ids: list[str],
                           actor: int) -> list[int | str]:
        if not unit_ids:
            return []
        units = [self._unit(state, uid) for uid in unit_ids]
        if any(unit["owner"] != actor or unit["exhausted"] for unit in units):
            return []
        destinations: list[int | str] = [0, 1, f"base:{actor}"]
        return [destination for destination in destinations
                if all(unit["location"] != destination for unit in units)]

    def move(self, state: dict, unit_ids: list[str], destination: int | str,
             actor: int) -> None:
        legal = self.legal_move_targets(state, unit_ids, actor)
        if destination not in legal:
            raise ReferenceRuleError("units are not jointly movable to destination")
        for unit_id in unit_ids:
            unit = self._unit(state, unit_id)
            origin = unit["location"]
            unit["location"] = destination
            unit["exhausted"] = True
            self._event(state, "move", unit=unit_id, origin=origin,
                        destination=destination, actor=actor)
        if isinstance(destination, int):
            enemies = [unit for unit in state["units"].values()
                       if unit["owner"] != actor and unit["location"] == destination]
            if state["fields"][destination]["controller"] != actor or enemies:
                state["phase"] = "showdown"
                state["actor"] = actor
                self._event(state, "showdown", field=destination, actor=actor)

    def choose_target(self, state: dict, target: str,
                      candidates: list[str]) -> None:
        if state.get("decision") is None:
            raise ReferenceRuleError("no target window")
        if target not in candidates:
            raise ReferenceRuleError("illegal target")
        state["decision"]["selected"] = target
        self._event(state, "target", target=target,
                    source=state["decision"].get("source"))
        state["decision"] = None

    def deal_damage(self, state: dict, unit_id: str, amount: int) -> None:
        if amount < 0:
            raise ReferenceRuleError("negative damage")
        unit = self._unit(state, unit_id)
        unit["damage"] += amount
        self._event(state, "damage", unit=unit_id, amount=amount,
                    total=unit["damage"])
        if unit["damage"] >= unit["might"]:
            self.destroy(state, unit_id)

    def destroy(self, state: dict, unit_id: str) -> None:
        unit = self._unit(state, unit_id)
        card = unit.get("card")
        card_owner = unit["card_owner"]
        del state["units"][unit_id]
        if card is not None:
            for row in state["players"]:
                for zone in ("main", "hand", "trash"):
                    if card in row[zone]:
                        row[zone].remove(card)
            state["players"][card_owner]["trash"].append(card)
        self._event(state, "death", unit=unit_id, card=card,
                    card_owner=card_owner)

    def transfer_control(self, state: dict, unit_id: str, new_owner: int) -> None:
        if new_owner not in (0, 1):
            raise ReferenceRuleError("invalid controller")
        unit = self._unit(state, unit_id)
        old_owner = unit["owner"]
        unit["owner"] = new_owner
        self._event(state, "control", unit=unit_id, old_owner=old_owner,
                    new_owner=new_owner, card_owner=unit["card_owner"])

    def recycle(self, state: dict, player: int, card_ids: list[str]) -> None:
        if player not in (0, 1):
            raise ReferenceRuleError("invalid player")
        row = state["players"][player]
        if any(card_id not in row["trash"] for card_id in card_ids):
            raise ReferenceRuleError("card is not in trash")
        for card_id in card_ids:
            row["trash"].remove(card_id)
            row["main"].append(card_id)
        self._event(state, "recycle", player=player, cards=list(card_ids))

    def push_chain(self, state: dict, effect: str, owner: int,
                   item_id: str | None = None) -> None:
        state["chain"].append({"effect": effect, "owner": owner,
                               "item": item_id})
        state["phase"] = "chain"
        state["actor"] = owner
        state["passes"] = 0
        self._event(state, "chain_push", effect=effect, owner=owner)

    def pass_priority(self, state: dict, player: int) -> None:
        if state["phase"] != "chain" or state["actor"] != player:
            raise ReferenceRuleError("player does not have chain priority")
        state["passes"] += 1
        self._event(state, "pass", player=player)
        if state["passes"] >= 2:
            item = state["chain"].pop()
            self._event(state, "chain_resolve", effect=item["effect"],
                        owner=item["owner"])
            state["passes"] = 0
            if not state["chain"]:
                state["phase"] = "main"
                state["actor"] = state["turn_player"]
        else:
            state["actor"] = 1 - player

    def queue_optional(self, state: dict, effect: str, player: int,
                       source: str) -> str:
        option_id = f"o{len(state['optional']) + 1}"
        state["optional"].append({"id": option_id, "effect": effect,
                                  "player": player, "source": source})
        state["phase"] = "optional"
        state["actor"] = player
        self._event(state, "optional_queue", id=option_id, effect=effect,
                    player=player, source=source)
        return option_id

    def choose_optional(self, state: dict, option_id: str, accept: bool) -> None:
        if state["phase"] != "optional":
            raise ReferenceRuleError("no optional window")
        index = next((i for i, item in enumerate(state["optional"])
                      if item["id"] == option_id), None)
        if index is None:
            raise ReferenceRuleError("unknown optional effect")
        item = state["optional"].pop(index)
        self._event(state, "optional_choice", id=option_id,
                    accept=bool(accept), effect=item["effect"])
        if not state["optional"]:
            state["phase"] = "main"
            state["actor"] = state["turn_player"]

    def canonical(self, state: dict) -> dict:
        result = deepcopy(state)
        result["units"] = {key: result["units"][key]
                           for key in sorted(result["units"])}
        result["events"] = deepcopy(result["events"])
        return result

