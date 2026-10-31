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


def certify(path: Path = DEFAULT_FIXTURES) -> dict:
    fixtures = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for fixture in fixtures:
        actual = run_fixture(fixture)
        failures = _compare(fixture.get("expected", {}), actual)
        results.append({"id": fixture["id"], "passed": not failures,
                        "failures": failures})
    return {"schema": "riftbound-reference-core-v1", "fixtures": results,
            "passed": all(item["passed"] for item in results)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run independent core golden scenarios")
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    args = parser.parse_args(argv)
    report = certify(args.fixtures)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

