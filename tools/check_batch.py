"""Exercise complete legal games and verify every replay; no network access."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from riftbound.engine import Environment, replay
from riftbound.origins import OriginsRules
from riftbound.policies import GreedyPolicy
from riftbound.training import RandomPolicy, self_play


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.seeds < 1:
        parser.error("seeds must be positive")
    rules, started, outcomes, actions = OriginsRules(), time.monotonic(), [], Counter()
    for name in ("greedy", "random"):
        for seed in range(args.seeds):
            env = Environment(rules, max_steps=3000)
            policies = (GreedyPolicy(), GreedyPolicy()) if name == "greedy" else (RandomPolicy(seed+100), RandomPolicy(seed+200))
            episode = self_play(env, policies, seed=seed)
            record = env.audit_replay()
            if replay(rules, record).audit_replay() != record:
                raise RuntimeError("replay mismatch")
            actions.update(a["kind"] for a in record["actions"])
            outcomes.append({"policy": name, "seed": seed, "steps": len(episode.decisions),
                             "terminated": episode.terminated, "truncated": episode.truncated})
            print(json.dumps(outcomes[-1]), flush=True)
    result = {"rules_id": rules.id, "games": len(outcomes), "replays_verified": len(outcomes),
              "terminated": sum(o["terminated"] for o in outcomes),
              "truncated": sum(o["truncated"] for o in outcomes),
              "seconds": round(time.monotonic()-started, 2), "actions": dict(actions), "results": outcomes}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
