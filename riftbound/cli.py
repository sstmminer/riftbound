"""Offline commands for the explicit Origins subset, not full Origins."""
import argparse
import json
from pathlib import Path
import platform
import sys

from .catalog import load_origins
from .engine import Environment, RulesUnavailable, replay
from .origins import OriginsRules
from .policies import GreedyPolicy
from .support import SUPPORTED, starter_deck, vision_deck
from .training import RandomPolicy, self_play


def positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def simulate(args):
    if args.export_decisions and args.output is None:
        raise ValueError("--export-decisions requires --output")
    decks = [json.loads(path.read_text(encoding="utf-8-sig")) if path else starter_deck()
             for path in (args.deck0, args.deck1)]
    rules = OriginsRules(decks)
    if args.output:
        if args.output.exists() and any(args.output.iterdir()):
            raise ValueError("output directory must be empty; existing files are not overwritten")
        args.output.mkdir(parents=True, exist_ok=True)
    results, wins, truncated = [], [0, 0], 0
    for game in range(args.games):
        seed = args.seed + game
        policies = ((GreedyPolicy(), GreedyPolicy()) if args.policy == "greedy" else
                    (RandomPolicy(seed+10000), RandomPolicy(seed+20000)))
        env = Environment(rules, max_steps=args.max_steps)
        episode = self_play(env, policies, seed=seed)
        obs = env.observe(0)
        if episode.terminated:
            wins[obs["winner"]] += 1
        else:
            truncated += 1
        result = {"game": game, "steps": len(episode.decisions), "turns": obs["turn"],
                  "points": obs["points"], "victory": obs["victory"], "winner": obs["winner"],
                  "terminated": episode.terminated, "truncated": episode.truncated}
        results.append(result)
        if args.output:
            write_json(args.output/f"replay-{game:04d}.json",
                       {"format": "riftbound-origins-replay-v1", "python": platform.python_version(),
                        "decks": rules.decks, "audit": env.audit_replay()})
            if args.export_decisions:
                with (args.output/f"decisions-{game:04d}.jsonl").open("x", encoding="utf-8") as stream:
                    for decision in episode.decisions:
                        stream.write(json.dumps({**decision, "rules_id": rules.id,
                                                 "final_rewards": episode.rewards,
                                                 "terminated": episode.terminated,
                                                 "truncated": episode.truncated}, ensure_ascii=False)+"\n")
        print(json.dumps(result), file=sys.stderr, flush=True)
    summary = {"scope": "Origins executable subset", "rules_id": rules.id,
               "games": args.games, "wins": wins, "truncated": truncated,
               "policy": args.policy, "results": results}
    if args.output:
        write_json(args.output/"summary.json", summary)
    print(json.dumps(summary, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Origins subset simulator (not full Origins support)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("status")
    gui = commands.add_parser("gui", help="launch the local Tk graphical client")
    gui.add_argument("--variant", choices=("starter", "vision"), default="starter")
    catalog = commands.add_parser("catalog")
    catalog.add_argument("--supported", action="store_true")
    deck_cmd = commands.add_parser("deck", help="print the included legal constructed deck")
    deck_cmd.add_argument("--output", type=Path)
    deck_cmd.add_argument("--variant", choices=("starter", "vision"), default="starter")
    validate = commands.add_parser("validate-deck")
    validate.add_argument("path", type=Path)
    sim = commands.add_parser("simulate")
    sim.add_argument("--games", type=positive, default=1)
    sim.add_argument("--seed", type=int, default=0)
    sim.add_argument("--policy", choices=("greedy", "random"), default="greedy")
    sim.add_argument("--max-steps", type=positive, default=3000)
    sim.add_argument("--deck0", type=Path)
    sim.add_argument("--deck1", type=Path)
    sim.add_argument("--output", type=Path, help="new/empty directory for summary and privileged replays")
    sim.add_argument("--export-decisions", action="store_true")
    verify = commands.add_parser("replay")
    verify.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "status":
            print(json.dumps({"version": "0.3.0", "rules": "RUP5-2026-10-09", "mode": "1v1 Duel",
                              "catalog_cards": len(load_origins()), "executable_cards": len(SUPPORTED),
                              "supported_subset_playable": True, "full_origins_supported": False,
                              "training_status": "experimental subset only; not a full-game benchmark"}, indent=2))
        elif args.command == "gui":
            from .gui import main as gui_main
            gui_main(variant=args.variant)
        elif args.command == "catalog":
            for card in load_origins():
                if not args.supported or card["code"] in SUPPORTED:
                    print(json.dumps({**card, "supported": card["code"] in SUPPORTED}, ensure_ascii=False))
        elif args.command == "deck":
            deck = vision_deck() if args.variant == "vision" else starter_deck()
            if args.output:
                write_json(args.output, deck)
            else:
                print(json.dumps(deck, indent=2))
        elif args.command == "validate-deck":
            deck = json.loads(args.path.read_text(encoding="utf-8-sig"))
            OriginsRules([deck, deck])
            print(json.dumps({"valid": True, "scope": "supported subset", "main": len(deck["main"])}))
        elif args.command == "replay":
            record = json.loads(args.path.read_text(encoding="utf-8"))
            if record["format"] != "riftbound-origins-replay-v1":
                raise ValueError("unsupported replay format")
            if record["python"].split(".")[:2] != platform.python_version().split(".")[:2]:
                raise ValueError("use the same Python major/minor version as the replay")
            env = replay(OriginsRules(record["decks"]), record["audit"])
            print(json.dumps({"verified": True, "steps": len(record["audit"]["actions"]),
                              "terminated": env.terminated, "truncated": env.truncated,
                              "rewards": env.rewards}))
        else:
            simulate(args)
        return 0
    except (ValueError, RulesUnavailable, OSError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
