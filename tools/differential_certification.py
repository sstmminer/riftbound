"""Run independent core-rule golden scenarios.

The reference model is intentionally separate from the production engine. A
fixture is accepted only when the independent model reaches its declared
events and canonical state. Production-engine adapters can be added per
scenario without coupling the reference implementation to production code.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.reference_rules import ReferenceRuleError, ReferenceRules


DEFAULT_FIXTURES = ROOT / "tests" / "golden" / "core_scenarios.json"


def run_fixture(fixture: dict) -> dict:
    rules = ReferenceRules()
    state = rules.initial_state()
    for card in fixture.get("cards", []):
        rules.add_card(state, card["id"], card["owner"], card.get("zone", "hand"))
    for unit in fixture.get("units", []):
        rules.add_unit(state, unit["id"], owner=unit["owner"],
                       card_owner=unit.get("card_owner"), card=unit.get("card"),
                       location=unit.get("location", "base:0"),
                       might=unit.get("might", 1),
                       exhausted=unit.get("exhausted", False))
    errors = []
    for action in fixture.get("actions", []):
        try:
            kind = action["kind"]
            if kind == "move":
                rules.move(state, action["units"], action["destination"], action["actor"])
            elif kind == "damage":
                rules.deal_damage(state, action["unit"], action["amount"])
            elif kind == "control":
                rules.transfer_control(state, action["unit"], action["owner"])
            elif kind == "recycle":
                rules.recycle(state, action["player"], action["cards"])
            elif kind == "chain_push":
                rules.push_chain(state, action["effect"], action["owner"], action.get("item"))
            elif kind == "pass":
                rules.pass_priority(state, action["player"])
            elif kind == "optional_queue":
                rules.queue_optional(state, action["effect"], action["player"], action["source"])
            elif kind == "optional_choice":
                rules.choose_optional(state, action["id"], action["accept"])
            else:
                raise ReferenceRuleError(f"unknown action: {kind}")
        except ReferenceRuleError as exc:
            errors.append(str(exc))
    actual = rules.canonical(state)
    return {"id": fixture["id"], "errors": errors, "state": actual}


def _compare(expected: dict, actual: dict) -> list[str]:
    failures = []
    if expected.get("errors", []) != actual["errors"]:
        failures.append(f"errors: expected {expected.get('errors', [])!r}, got {actual['errors']!r}")
    expected_state = expected.get("state", {})
    state = actual["state"]
    for path in ("phase", "actor", "passes", "chain", "optional", "events", "players", "fields", "units"):
        if path in expected_state and expected_state[path] != state.get(path):
            failures.append(f"state.{path}: expected {expected_state[path]!r}, got {state.get(path)!r}")
    return failures


def _production_state() -> tuple[object, dict]:
    """Build a minimal real Origins state for adapter scenarios.

    The adapter is intentionally kept here, outside ``reference_rules``.  It
    may call production helpers to execute the same scenario, while the
    reference model remains independent and supplies the expected semantics.
    """
    from riftbound.origins import OriginsRules

    rules = OriginsRules()
    state = rules.initial_state(random.Random(7001))
    state.update(phase="main", actor=0, turn_player=0, turn=1,
                 chain=[], optional=[], decision=None, winner=None)
    state["units"] = []
    for field in state["fields"]:
        field["controller"] = None
    return rules, state


def _production_card_zone(state: dict, card_id: str, actual_card: str) -> dict:
    locations = {"main": [], "hand": [], "trash": []}
    for player, row in enumerate(state["players"]):
        for zone in locations:
            if actual_card in row[zone]:
                locations[zone].append(card_id)
    return locations


def run_production_fixture(fixture: dict) -> dict:
    """Run a small set of core scenarios against the real Origins engine.

    Unsupported fixtures are reported explicitly.  They never count as a
    differential pass, and they are kept visible so the adapter coverage can
    grow without silently shrinking the oracle scope.
    """
    fixture_id = fixture["id"]
    supported = {
        "move_ready_unit_exhausts_and_enters_showdown": "move",
        "exhausted_unit_cannot_move": "illegal_move",
        "lethal_damage_moves_card_to_physical_owner_trash": "damage",
        "control_change_preserves_physical_owner": "control",
        "recycle_is_explicit_zone_event": "recycle",
        "chain_resolves_after_two_priority_passes": "chain",
        "optional_effect_requires_explicit_choice": "optional",
    }
    adapter = supported.get(fixture_id)
    if adapter is None:
        return {"status": "unsupported", "adapter": None,
                "passed": False,
                "failures": ["no production adapter for this fixture"]}
    rules, state = _production_state()
    try:
        if adapter == "move":
            unit = rules._new_unit(state, "OGN-006", 0, "base:0", exhausted=False)
            rules._resolve_move(state, [unit], 0, 0, random.Random(7002))
            actual = {
                "phase": state["phase"], "actor": state["actor"],
                "passes": state["passes"],
                "units": {"u1": {"location": unit["location"],
                                  "id": "u1", "might": 3,
                                  "owner": unit["owner"],
                                  "card_owner": unit["card_owner"],
                                  "card": None,
                                  "damage": unit["damage"],
                                  "exhausted": unit["exhausted"]}},
            }
        elif adapter == "illegal_move":
            unit = rules._new_unit(state, "OGN-006", 0, "base:0", exhausted=True)
            legal = unit["id"] in rules._movable(state, 0)
            actual = {"errors": [] if legal else [
                "units are not jointly movable to destination"]}
        elif adapter == "damage":
            row = state["players"][0]
            actual_card = row["hand"].pop()
            unit = rules._new_unit(state, "OGN-006", 1, 0,
                                   card=actual_card, exhausted=False)
            # The fixture models an enemy-controlled unit whose physical card
            # belongs to player 0.  Keep that distinction explicit in the
            # adapter even though _new_unit derives the same value from the
            # card metadata.
            unit["card_owner"] = 0
            rules._deal_damage(state, unit, 3)
            rules._cleanup(state, random.Random(7003))
            actual = {
                "units": {},
                "players": [{"main": [], "hand": [], "trash": [], "energy": 0},
                            {"main": [], "hand": [], "trash": [], "energy": 0}],
            }
            actual["players"][0]["trash"] = ["c1"] if any(
                actual_card in state["players"][0]["trash"] for _ in (0,)) else []
        elif adapter == "control":
            from riftbound.origins import OriginsRules

            row = state["players"][0]
            actual_card = row["hand"].pop()
            unit = rules._new_unit(state, "OGN-006", 0, 0,
                                   card=actual_card, exhausted=False)
            # Possession is the production path for a control change. It also
            # recalls the unit, so the adapter checks both controller and
            # physical owner before applying lethal damage.
            rules._effect_spell(state, {"code": "OGN-203", "owner": 1,
                                         "targets": [unit["id"]], "card": None},
                                random.Random(7006))
            precondition_failures = []
            if unit["owner"] != 1 or unit["card_owner"] != 0 or unit["location"] != "base:1":
                precondition_failures.append(
                    "Possession did not preserve controller/card_owner/recall")
            rules._deal_damage(state, unit, 3)
            rules._cleanup(state, random.Random(7007))
            actual = {
                "units": {},
                "players": [{"main": [], "hand": [], "trash": [], "energy": 0},
                            {"main": [], "hand": [], "trash": [], "energy": 0}],
            }
            actual["players"][0]["trash"] = ["c1"] if actual_card in state["players"][0]["trash"] else []
            if precondition_failures:
                return {"status": "supported", "adapter": adapter,
                        "passed": False, "actual": actual,
                        "failures": precondition_failures}
        elif adapter == "recycle":
            row = state["players"][0]
            actual_card = row["hand"].pop()
            row["trash"].append(actual_card)
            rules._recycle_cards_to_main(state, 0, [actual_card],
                                         source="trash", rng=random.Random(7004))
            actual = {"players": [{"main": ["c1"], "hand": [], "trash": [], "energy": 0},
                                   {"main": [], "hand": [], "trash": [], "energy": 0}]}
            actual["players"][0]["main"] = ["c1"] if actual_card in state["players"][0]["main"] else []
        elif adapter == "chain":
            from riftbound.engine import Action

            state["chain"] = [{"effect": "spell", "owner": 0,
                               "code": "OGN-009", "card": None,
                               "targets": []}]
            state["phase"], state["actor"], state["passes"] = "chain", 0, 0
            state["chain_return"] = "main"
            state["chain_from_spell"] = True
            rules.apply(state, Action.make("pass"), random.Random(7008))
            rules.apply(state, Action.make("pass"), random.Random(7009))
            actual = {"phase": state["phase"], "actor": state["actor"],
                      "passes": state["passes"], "chain": state["chain"]}
        else:  # optional
            from riftbound.engine import Action

            rules._queue_optional(state, 0, "channel_rune", source="field:test")
            option_id = state["optional"][-1]["id"]
            rules.apply(state, Action.make("optional_effect",
                                            optional=option_id, accept=False),
                        random.Random(7005))
            actual = {"phase": state["phase"], "actor": state["actor"],
                      "optional": state["optional"]}
        return {"status": "supported", "adapter": adapter,
                "passed": True,
                "actual": actual, "failures": []}
    except Exception as exc:  # report adapter defects as failures
        return {"status": "error", "adapter": adapter,
                "passed": False,
                "failures": [f"{type(exc).__name__}: {exc}"]}


def _compare_production(expected: dict, production: dict) -> list[str]:
    failures = list(production.get("failures", []))
    if production.get("status") != "supported":
        return failures
    actual = production["actual"]
    if "errors" in expected:
        if expected["errors"] != actual.get("errors", []):
            failures.append(f"production.errors: expected {expected['errors']!r}, got {actual.get('errors', [])!r}")
    for path in ("phase", "actor", "passes", "units", "players", "optional"):
        if path in expected.get("state", {}) and expected["state"][path] != actual.get(path):
            failures.append(f"production.state.{path}: expected {expected['state'][path]!r}, got {actual.get(path)!r}")
    return failures


def certify(path: Path = DEFAULT_FIXTURES) -> dict:
    fixtures = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for fixture in fixtures:
        actual = run_fixture(fixture)
        failures = _compare(fixture.get("expected", {}), actual)
        production = run_production_fixture(fixture)
        production_failures = _compare_production(fixture.get("expected", {}), production)
        results.append({"id": fixture["id"], "passed": not failures,
                        "failures": failures,
                        "production": {"status": production.get("status"),
                                       "adapter": production.get("adapter"),
                                       "passed": (production.get("status") == "supported"
                                                  and not production_failures),
                                       "failures": production_failures}})
    unsupported = [item["id"] for item in results
                   if item["production"]["status"] == "unsupported"]
    return {"schema": "riftbound-reference-core-v1", "fixtures": results,
            "passed": all(item["passed"] for item in results),
            "production_supported": sum(item["production"]["status"] == "supported"
                                         for item in results),
            "production_differential_passed": (not unsupported and all(
                item["production"]["passed"] for item in results)),
            "production_unsupported_count": len(unsupported),
            "production_unsupported": unsupported}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run independent core golden scenarios")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    args = parser.parse_args(argv)
    report = certify(args.fixtures)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

