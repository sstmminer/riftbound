"""Build an explicit Origin certification report.

The stable baseline proves that the current executable paths make progress and
replay deterministically.  It does not prove that every card interaction has
been adjudicated.  This tool adds the missing evidence layer: catalog/support
partition checks, AbilityRegistry integrity, the runtime gate, and an explicit
list of unresolved rule-difference blockers.  A report is certified only when
that blocker list is empty; the tool never infers certification from card text
or from the size of ``SUPPORTED`` alone.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from riftbound.abilities import ORIGINS_ABILITIES
from riftbound.catalog import load_origins
from riftbound.support import (
    ACCELERATE, FIELD_CODES, GEAR_CODES, HIDDEN_CODES, LEGENDS, LEGEND,
    REACTIONS, RUNES, SPELL_CODES, SPRITE_TOKEN, TOKEN, TOKEN_CODES,
    UNIT_CODES, SUPPORTED,
)
from tools.stable_baseline import build_report


PARTITIONS = {
    "unit": UNIT_CODES,
    "gear": GEAR_CODES,
    "spell": SPELL_CODES,
    "field": FIELD_CODES,
    "legend": LEGENDS | {LEGEND},
    "rune": RUNES,
    "token": TOKEN_CODES | {TOKEN, SPRITE_TOKEN},
}

# These are deliberately mechanism-level entries.  They are closed only after
# a rule/FAQ scenario and a regression test demonstrate the complete behavior.
# Keeping them here makes an incomplete certification visible in CI and in
# machine-readable reports instead of silently calling all registered cards
# "complete".
KNOWN_BLOCKERS = (
    {
        "id": "independent_rules_oracle",
        "scope": "all Origins",
        "description": "No independent second rules engine or official judge oracle for full differential certification.",
    },
    {
        "id": "cross_region_control_and_nested_play",
        "scope": "control changes, nested free plays, Jinx/Karma sources",
        "description": "Complex cross-region ownership/control and nested free-play combinations lack complete differential coverage.",
    },
    {
        "id": "registry_recursive_replacement",
        "scope": "AbilityRegistry",
        "description": "Recursive copying and a subset of replacement/event abilities still rely on specialized paths.",
    },
    {
        "id": "battlefield_optional_matrix",
        "scope": "Origins battlefields",
        "description": "Some simultaneous battlefield optional effects do not yet have a complete interaction matrix.",
    },
)


def catalog_audit() -> dict:
    cards = load_origins()
    catalog = {card["code"] for card in cards}
    expected = {f"OGN-{number:03d}" for number in range(1, 299)}
    memberships: dict[str, list[str]] = {code: [] for code in catalog}
    for category, codes in PARTITIONS.items():
        for code in codes:
            if code in memberships:
                memberships[code].append(category)
    duplicate_membership = sorted(code for code, categories in memberships.items()
                                  if len(categories) != 1)
    unclassified = sorted(code for code, categories in memberships.items() if not categories)
    unknown_partition_codes = sorted(set().union(*PARTITIONS.values()) - catalog)
    missing_catalog_codes = sorted(expected - catalog)
    unsupported = sorted(catalog - SUPPORTED)
    extra_supported = sorted(SUPPORTED - catalog)
    type_counts: dict[str, int] = {}
    for card in cards:
        kind = str(card.get("type", "unknown"))
        type_counts[kind] = type_counts.get(kind, 0) + 1
    return {
        "catalog_cards": len(cards),
        "expected_cards": len(expected),
        "catalog_hash_verified": True,
        "missing_catalog_codes": missing_catalog_codes,
        "unknown_partition_codes": unknown_partition_codes,
        "duplicate_membership": duplicate_membership,
        "unclassified_codes": unclassified,
        "unsupported_codes": unsupported,
        "extra_supported_codes": extra_supported,
        "type_counts": type_counts,
        "partition_complete": (catalog == expected and not unknown_partition_codes
                                and not duplicate_membership and not unclassified
                                and not unsupported and not extra_supported),
    }


def registry_audit() -> dict:
    specs = ORIGINS_ABILITIES.all()
    source_codes = {code for spec in specs for code in spec.source_codes}
    catalog = {card["code"] for card in load_origins()}
    invalid_sources = sorted(source_codes - catalog)
    missing_action_ids = sorted(spec.ability_id for spec in specs if not spec.action_kind)
    duplicate_sources = sorted(
        code for code in source_codes
        if sum(code in spec.source_codes for spec in specs) > 1
    )
    return {
        "specs": len(specs),
        "copyable_specs": sum(spec.copyable for spec in specs),
        "exhaust_specs": sum(spec.requires_exhaust for spec in specs),
        "invalid_source_codes": invalid_sources,
        "missing_action_ids": missing_action_ids,
        "duplicate_source_codes": duplicate_sources,
        "integrity": not invalid_sources and not missing_action_ids,
    }


def build_certification(*, seeds: int, max_steps: int, policies: tuple[str, ...],
                        run_tests: bool = True) -> dict:
    started = time.monotonic()
    catalog = catalog_audit()
    registry = registry_audit()
    runtime = build_report(seeds=seeds, max_steps=max_steps, policies=policies,
                           run_tests=run_tests)
    blockers = [dict(item, status="open") for item in KNOWN_BLOCKERS]
    checks = {
        "catalog_partition": catalog["partition_complete"],
        "ability_registry": registry["integrity"],
        "runtime_gate": runtime["gate"]["passed"],
        "known_blockers_closed": not blockers,
    }
    return {
        "schema": "riftbound-origins-certification-v1",
        "rules_id": runtime["rules_id"],
        "scope": "Origins / two-player standard constructed",
        "catalog": catalog,
        "ability_registry": registry,
        "runtime": runtime,
        "known_blockers": blockers,
        "checks": {**checks, "certified": all(checks.values())},
        "seconds": round(time.monotonic() - started, 3),
    }


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the Origin certification report")
    parser.add_argument("--seeds", type=_positive, default=3)
    parser.add_argument("--max-steps", type=_positive, default=3000)
    parser.add_argument("--policies", default="greedy,random")
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    policies = tuple(name.strip() for name in args.policies.split(",") if name.strip())
    if not policies or any(name not in {"greedy", "random"} for name in policies):
        parser.error("policies must contain only greedy and random")
    report = build_certification(seeds=args.seeds, max_steps=args.max_steps,
                                 policies=policies, run_tests=not args.skip_tests)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["checks"]["certified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
