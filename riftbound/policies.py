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
        if phase == "optional":
            # Optional effects are explicit rules windows. If several same-
            # player effects arrived together, choose their order first;
            # otherwise accept the current effect as the deterministic baseline.
            ordered = [a for a, _ in options if a.kind == "order_optional"]
            if ordered:
                return ordered[0]
            return next(a for a, args in options
                        if a.kind == "optional_effect" and args.get("accept"))
        if phase == "decision":
            if obs["decision"].get("accelerate"):
                # Accelerate opens a narrow play-time payment window.  Use
                # available rune Add-resource reactions before accepting the
                # replacement; never fall through to the hand-card chooser,
                # because these actions intentionally have no ``card`` arg.
                row = obs["players"][player]
                domains = set(obs["decision"]["accelerate"].get("domains", []))
                if row["energy"] < 1:
                    rune_action = next((a for a, args in options
                                        if a.kind == "exhaust_rune"), None)
                    if rune_action is not None:
                        return rune_action
                if not any(power in domains for power in row.get("power", [])):
                    rune_action = next((a for a, args in options
                                        if a.kind == "recycle_rune"
                                        and self.cards.get(next((r["code"] for r in row.get("runes", [])
                                                                  if r["id"] == args.get("rune")), ""),
                                                           {}).get("domains", [None])[0] in domains), None)
                    if rune_action is not None:
                        return rune_action
                return next((a for a, args in options
                             if a.kind == "choose_option" and args.get("option") == "accelerate"),
                            next(a for a, _ in options if a.kind == "choose_option"))
            if obs["decision"]["kind"] == "predict":
                return next(a for a, args in options if not args["recycle"])
            if obs["decision"]["kind"] == "choice":
                # Accelerate is a play-time payment window.  Resource Add
                # reactions may be used while it is open, so do not assume
                # every legal action carries a card argument (the old branch
                # below is for discard-card choices only).
                if obs["decision"].get("accelerate"):
                    pending = obs["decision"]["accelerate"]
                    row = obs["players"][player]
                    domains = set(pending.get("domains", []))
                    matching_power = any(power in domains or power == "any"
                                         for power in row.get("power", []))
                    if row.get("energy", 0) < 1:
                        exhaust = [a for a, _ in options if a.kind == "exhaust_rune"]
                        if exhaust:
                            return exhaust[0]
                    if not matching_power:
                        recycle = [a for a, args in options
                                    if a.kind == "recycle_rune"
                                    and (args.get("rune") in {
                                        rune["id"] for rune in row.get("runes", [])
                                        if rune.get("code") in domains
                                    })]
                        if recycle:
                            return recycle[0]
                    accelerate = [a for a, args in options
                                  if a.kind == "choose_option" and args.get("option") == "accelerate"]
                    if accelerate and row.get("energy", 0) >= 1 and matching_power:
                        return accelerate[0]
                    skip = [a for a, args in options
                            if a.kind == "choose_option" and args.get("option") == "skip"]
                    if skip:
                        return skip[0]
                # Other choice windows (for example Udyr) are deterministic
                # enough for a smoke-test policy; pick the first option.
                return next(a for a, _ in options if a.kind == "choose_option")
            if obs["decision"]["kind"] in {"target", "unit_target"}:
                if obs["decision"]["kind"] == "unit_target":
                    return next(a for a, _ in options if a.kind == "choose_target")
                if obs["decision"].get("multi"):
                    selected = set(obs["decision"].get("selected", []))
                    if len(selected) < obs["decision"].get("min", 1):
                        return next(a for a, args in options if a.kind == "choose_target")
                    if len(selected) < obs["decision"].get("max", len(selected)):
                        choices = [a for a, _ in options if a.kind == "choose_target"]
                        if choices:
                            return choices[0]
                    return next(a for a, _ in options if a.kind == "confirm_targets")
                return next(a for a, _ in options if a.kind == "choose_target")
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
