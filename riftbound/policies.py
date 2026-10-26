"""Baseline policy using only the current player's observation and legal actions."""
import json

from .catalog import load_origins


class GreedyPolicy:
    """A reproducible smoke-test opponent, not a competitive strategy."""

    def __init__(self):
        self.cards = {row["code"]: row for row in load_origins()}

    def choose(self, observation, legal_actions):
        obs = observation
        player = obs["player"]
        phase = obs["phase"]
        options = [(action, json.loads(action.arguments)) for action in legal_actions]
        if phase == "decision":
            if obs["decision"]["kind"] == "predict":
                return next(a for a, args in options if not args["recycle"])
            own = {c["id"]: c["code"] for c in obs["hand"]}
            return max(options, key=lambda pair: self.cards[own[pair[1]["card"]]]["energy"])[0]
        if phase == "mulligan":
            expensive = [i for i, card in enumerate(obs["hand"]) if self.cards[card["code"]]["energy"] >= 6][:2]
            return next(a for a, args in options if args["slots"] == expensive)
        if phase == "trigger_order":
            return legal_actions[0]
        if phase == "move_select":
            selected = [a for a, _ in options if a.kind == "select_unit"]
            return selected[0] if selected else next(a for a, _ in options if a.kind == "commit_move")
        if phase == "damage":
            targets = {u["id"]: u for u in obs["units"]}
            return max(options, key=lambda pair: targets[pair[1]["target"]]["might"])[0]
        units = {u["id"]: u for u in obs["units"]}
        own_cards = {c["id"]: c["code"] for c in obs["hand"] + obs["players"][player]["champion"]}
        if phase == "main":
            taps = [a for a, _ in options if a.kind == "exhaust_rune"]
            if taps:
                return taps[0]
            plays = [(a, args) for a, args in options if a.kind == "play_unit"]
            if plays:
                return max(plays, key=lambda pair: (
                    self.cards[own_cards[pair[1]["card"]]]["might"], pair[1]["accelerate"],
                    isinstance(pair[1]["location"], int)))[0]
        # Prefer useful spells; avoid damaging our own units or buffing enemies.
        spells = []
        for action, args in options:
            if action.kind != "play_spell":
                continue
            code = own_cards[args["card"]]
            damage = code in {"OGN-009", "OGN-024"}
            if all((units[t]["owner"] != player) == damage for t in args["targets"]):
                spells.append((action, args))
        if spells:
            return spells[0][0]
        if phase in {"chain", "showdown"}:
            # Keep the policy simple: resource abilities can still be used to
            # prepare a known Reaction if we have one; never inspect hidden hand.
            if any(c["code"] in {"OGN-206", "OGN-207"} for c in obs["hand"]):
                taps = [a for a, _ in options if a.kind == "exhaust_rune"]
                if taps:
                    return taps[0]
            return next(a for a, _ in options if a.kind == "pass")
        legend = [a for a, _ in options if a.kind == "legend_energy"]
        if legend:
            return legend[0]
        # Recycle exhausted runes only if a card we can plausibly play needs power.
        row = obs["players"][player]
        wants_power = any(self.cards[c["code"]]["power_cost"] > len(row["power"])
                          and self.cards[c["code"]]["energy"] <= row["energy"] for c in obs["hand"] + row["champion"])
        if wants_power:
            exhausted = {r["id"] for r in row["runes"] if r["exhausted"]}
            recycling = [a for a, args in options if a.kind == "recycle_rune" and args["rune"] in exhausted]
            if recycling:
                return recycling[0]
        moves = [(a, args) for a, args in options if a.kind == "begin_move" and isinstance(args["destination"], int)]
        if moves:
            # Empty/hostile fields before reinforcing a field already controlled.
            return min(moves, key=lambda pair: obs["fields"][pair[1]["destination"]]["controller"] == player)[0]
        return next(a for a, _ in options if a.kind == "end_turn")
