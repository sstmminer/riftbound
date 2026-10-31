"""Run the reproducible Origin stability gate.

This is a release-gate tool, not a playing policy. It runs the test suite,
then exercises fixed-seed games with trusted baseline policies and checks that
every game has legal progress, reaches a real terminal state, and can be
replayed through the engine audit record.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
from pathlib import Path
import re
import subprocess
import sys
import time

# Support both ``python tools/stable_baseline.py`` and
# ``python -m tools.stable_baseline`` from the repository root without
# requiring an editable install first.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from riftbound.catalog import load_origins
from riftbound.engine import Environment, canonical, replay
from riftbound.origins import OriginsRules
from riftbound.policies import GreedyPolicy
from riftbound.support import SUPPORTED
from riftbound.training import RandomPolicy


POLICY_NAMES = ("greedy", "random")


def _positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def _policy_pair(name: str, seed: int):
    if name == "greedy":
        return GreedyPolicy(), GreedyPolicy()
    if name == "random":
        return RandomPolicy(seed + 100), RandomPolicy(seed + 200)
    raise ValueError(f"unknown policy: {name}")


def _semantic_digest(env: Environment) -> str:
    """Hash gameplay state without RNG or allocation-only counters."""
    state = copy.deepcopy(env._state)  # trusted release-gate inspection only
    state.pop("next_object", None)
    return canonical(state)


def _run_tests() -> dict:
    started = time.monotonic()
    command = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]
    completed = subprocess.run(command, text=True, capture_output=True)
    output = (completed.stdout + completed.stderr).strip()
    match = re.search(r"Ran (\d+) tests?", output)
    return {
        "command": " ".join(command),
        "passed": completed.returncode == 0,
        "returncode": completed.returncode,
        "tests": int(match.group(1)) if match else None,
        "seconds": round(time.monotonic() - started, 3),
        "output_tail": output[-4000:],
    }


def run_game(rules, policy_name: str, seed: int, max_steps: int) -> dict:
    """Run one game while retaining enough evidence to diagnose a failure."""
    env = Environment(rules, max_steps=max_steps)
    started = time.monotonic()
    actions = Counter()
    seen_digests: set[str] = set()
    repeated_states = 0
    failure = None
    deadlock = False
    replay_verified = False
    steps = 0
    try:
        env.reset(seed=seed)
        policies = _policy_pair(policy_name, seed)
        while not env.done:
            digest = _semantic_digest(env)
            if digest in seen_digests:
                # Rune rollback and other legal reversible actions can return
                # to an earlier semantic state. A repeated state is recorded
                # for diagnosis; a real cycle will eventually become an
                # unexpected truncation under the step cap.
                repeated_states += 1
            seen_digests.add(digest)
            player = env.current_player
            legal = env.legal_actions()
            if not legal:
                failure = "nonterminal state exposed no legal actions"
                deadlock = True
                break
            action = policies[player].choose(env.observe(player), legal)
            if action not in legal:
                failure = "policy returned an illegal action"
                break
            env.step(action)
            actions[action.kind] += 1
            steps += 1
        if failure is None and not env.done:
            failure = "game stopped without terminal or truncation state"
        if failure is None:
            record = env.audit_replay()
            replay_verified = replay(rules, record).audit_replay() == record
            if not replay_verified:
                failure = "replay mismatch"
    except Exception as error:  # keep all seeds in the report
        failure = f"{type(error).__name__}: {error}"

    result = {
        "policy": policy_name,
        "seed": seed,
        "steps": steps,
        "terminated": bool(env.terminated),
        "truncated": bool(env.truncated),
        "deadlock": deadlock,
        "repeated_states": repeated_states,
        "replay_verified": replay_verified,
        "actions": dict(actions),
        "seconds": round(time.monotonic() - started, 3),
    }
    if failure:
        result["failure"] = failure
    return result


def build_report(*, seeds: int, max_steps: int, policies: tuple[str, ...],
                 run_tests: bool = True) -> dict:
    started = time.monotonic()
    rules = OriginsRules()
    results = []
    action_counts = Counter()
    for policy_name in policies:
        for seed in range(seeds):
            result = run_game(rules, policy_name, seed, max_steps)
            results.append(result)
            action_counts.update(result["actions"])
            print(json.dumps(result, ensure_ascii=False), file=sys.stderr, flush=True)

    tests = _run_tests() if run_tests else {"skipped": True}
    terminated = sum(result["terminated"] for result in results)
    truncated = sum(result["truncated"] for result in results)
    failures = [result for result in results if "failure" in result]
    deadlocks = sum(result["deadlock"] for result in results)
    replay_mismatches = sum(not result["replay_verified"] for result in results)
    gate = {
        "tests_passed": tests.get("passed", True),
        "no_failures": not failures,
        "deadlocks": deadlocks == 0,
        "replays_verified": replay_mismatches == 0,
        "no_truncation": truncated == 0,
    }
    return {
        "schema": "riftbound-origins-stability-v1",
        "rules_id": rules.id,
        "catalog_cards": len(load_origins()),
        "executable_cards": len(SUPPORTED),
        "full_origins_supported": False,
        "parameters": {"seeds": seeds, "max_steps": max_steps,
                        "policies": list(policies)},
        "tests": tests,
        "games": {
            "total": len(results),
            "terminated": terminated,
            "truncated": truncated,
            "deadlocks": deadlocks,
            "replay_mismatches": replay_mismatches,
            "actions": dict(action_counts),
            "results": results,
        },
        "gate": {**gate, "passed": all(gate.values())},
        "seconds": round(time.monotonic() - started, 3),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Origin stable-baseline release gate")
    parser.add_argument("--seeds", type=_positive, default=10,
                        help="number of fixed seeds per policy (default: 10)")
    parser.add_argument("--max-steps", type=_positive, default=3000)
    parser.add_argument("--policies", default=",".join(POLICY_NAMES),
                        help="comma-separated policies: greedy,random")
    parser.add_argument("--skip-tests", action="store_true",
                        help="skip unittest discovery; useful for local iteration")
    parser.add_argument("--output", type=Path,
                        help="write the JSON report; existing files are rejected")
    args = parser.parse_args(argv)
    policies = tuple(name.strip() for name in args.policies.split(",") if name.strip())
    if not policies or any(name not in POLICY_NAMES for name in policies):
        parser.error("policies must contain only greedy and random")
    report = build_report(seeds=args.seeds, max_steps=args.max_steps,
                          policies=policies, run_tests=not args.skip_tests)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["gate"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
