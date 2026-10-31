"""Independent structural checks for an Origins state.

This module intentionally does not import :class:`OriginsRules` or call its
``validate`` method.  It is a small contract checker for release tests: it
can catch conservation, ownership, visibility and phase-shape regressions
without becoming a second rules engine.  Passing it therefore narrows the
risk surface, but it cannot replace a second rules implementation or an
official judge oracle.
"""
from __future__ import annotations

from collections import Counter


_PHASES = {
    "mulligan", "legend", "main", "chain", "trigger_order", "optional",
    "decision", "reveal", "battle", "showdown", "combat", "damage",
    "move_select", "end",
}
_POWER_DOMAINS = {"fury", "calm", "chaos", "mind", "order", "body", "any", "spell_any"}


def _card_refs(state):
    """Yield every physical non-rune card reference in the live state."""
    seen = set()
    for row in state.get("players", []):
        for zone in ("main", "hand", "champion", "trash", "banishment"):
            for uid in row.get(zone, ()):
                seen.add(uid)
                yield uid
        for gear in row.get("gear", ()):
            if gear.get("card") is not None:
                seen.add(gear["card"])
                yield gear["card"]
        for hidden in row.get("hidden", ()):
            if hidden.get("card") is not None:
                seen.add(hidden["card"])
                yield hidden["card"]
    for unit in state.get("units", ()):
        if unit.get("card") is not None:
            seen.add(unit["card"])
            yield unit["card"]
    for item in state.get("chain", ()):
        if item.get("card") is not None:
            seen.add(item["card"])
            yield item["card"]
    decision = state.get("decision") or {}
    item = decision.get("item") or {}
    if item.get("card") is not None and item["card"] not in seen:
        seen.add(item["card"])
        yield item["card"]
    reveal = state.get("reveal") or {}
    item = reveal.get("item") or {}
    if item.get("card") is not None and item["card"] not in seen:
        yield item["card"]


def violations(state) -> list[str]:
    """Return independent state-contract violations.

    The function is deliberately conservative: it reports only properties
    that must hold for every legal state, and never attempts to adjudicate a
    card effect or infer a target.  An empty list means the state passed the
    independent structural contract.
    """
    errors: list[str] = []
    players = state.get("players")
    if not isinstance(players, list) or len(players) != 2:
        return ["players must contain exactly two entries"]

    if state.get("actor") not in (0, 1) or state.get("turn_player") not in (0, 1):
        errors.append("actor/turn_player out of range")
    if state.get("phase") not in _PHASES:
        errors.append("unknown phase")

    cards = state.get("cards")
    if not isinstance(cards, dict):
        errors.append("cards must be a mapping")
        cards = {}
    for uid, card in cards.items():
        if not isinstance(card, dict) or card.get("owner") not in (0, 1):
            errors.append(f"invalid card owner: {uid}")

    refs = list(_card_refs(state))
    if len(refs) != len(set(refs)):
        errors.append("physical card referenced more than once")
    if Counter(refs) != Counter(cards.keys()):
        errors.append("physical card conservation mismatch")

    for player, row in enumerate(players):
        runes = list(row.get("runes", ())) + list(row.get("rune_deck", ()))
        rune_ids = [rune.get("id") for rune in runes]
        if len(runes) != 12 or len(rune_ids) != len(set(rune_ids)):
            errors.append(f"rune conservation failed for player {player}")
        if not isinstance(row.get("energy"), int) or row["energy"] < 0:
            errors.append(f"invalid energy for player {player}")
        if any(power not in _POWER_DOMAINS for power in row.get("power", ())):
            errors.append(f"invalid rune power for player {player}")
        for gear in row.get("gear", ()):
            if gear.get("owner") != player or gear.get("location") != f"base:{player}":
                errors.append("gear ownership/location mismatch")
        for hidden in row.get("hidden", ()):
            if hidden.get("owner", player) != player:
                errors.append("hidden card ownership mismatch")

    units = state.get("units", ())
    unit_ids = [unit.get("id") for unit in units]
    if len(unit_ids) != len(set(unit_ids)):
        errors.append("duplicate unit object id")
    fields = state.get("fields", ())
    field_count = len(fields)
    occupants = {index: set() for index in range(field_count)}
    for unit in units:
        owner = unit.get("owner")
        if owner not in (0, 1):
            errors.append("unit owner out of range")
        location = unit.get("location")
        valid_location = (isinstance(location, int) and 0 <= location < field_count)
        valid_location = valid_location or location == f"base:{owner}"
        if not valid_location:
            errors.append("invalid unit location")
        elif isinstance(location, int):
            occupants[location].add(owner)
        for key in ("damage", "temporary", "assault", "combat_shield", "buff"):
            if not isinstance(unit.get(key), int) or unit[key] < 0:
                errors.append(f"invalid unit counter: {key}")
        if not isinstance(unit.get("exhausted"), bool):
            errors.append("invalid unit exhausted flag")
        if not isinstance(unit.get("stunned"), bool):
            errors.append("invalid unit stunned flag")
    if state.get("phase") == "main":
        for index, field in enumerate(fields):
            controller = field.get("controller")
            if controller not in (None, 0, 1):
                errors.append(f"invalid field controller: {index}")
            if controller is not None and controller not in occupants[index]:
                errors.append(f"field controller without occupant: {index}")

    optional = state.get("optional", ())
    if state.get("phase") == "optional":
        if not optional or optional[0].get("player") != state.get("actor"):
            errors.append("optional priority mismatch")
    elif optional:
        errors.append("optional effects outside optional phase")
    decision = state.get("decision")
    if decision is not None and decision.get("player") not in (0, 1):
        errors.append("decision player out of range")
    reveal = state.get("reveal")
    if reveal is not None:
        if reveal.get("kind") not in {"display", "select"}:
            errors.append("invalid reveal kind")
        if any(uid not in cards for uid in reveal.get("cards", ())):
            errors.append("unknown revealed card")
    return errors


def assert_valid(state) -> None:
    """Raise ``ValueError`` with all independent contract failures."""
    errors = violations(state)
    if errors:
        raise ValueError("; ".join(errors))

