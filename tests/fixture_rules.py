"""Synthetic test backend. This is NOT Riftbound or a proposed rules subset."""

from riftbound.engine import Action


class FixtureRules:
    id = "synthetic-test-only/v1"

    def initial_state(self, rng):
        return {"player": 0, "scores": [0, 0],
                "hands": [[rng.randint(1, 3) for _ in range(3)] for _ in range(2)]}

    def player(self, state):
        return state["player"]

    def legal_actions(self, state):
        return tuple(Action.make("collect", slot=i) for i in range(3))

    def observe(self, state, player):
        return {"player": player, "to_act": state["player"],
                "scores": state["scores"], "hand": state["hands"][player],
                "opponent_hand_size": len(state["hands"][1-player])}

    def apply(self, state, action, rng):
        import json
        player = state["player"]
        slot = json.loads(action.arguments)["slot"]
        state["scores"][player] += state["hands"][player][slot]
        state["hands"][player][slot] = rng.randint(1, 3)
        state["player"] = 1-player

    def outcome(self, state):
        for player, score in enumerate(state["scores"]):
            if score >= 8:
                return (1.0, -1.0) if player == 0 else (-1.0, 1.0)
        return None

    def validate(self, state):
        assert state["player"] in (0, 1)
        assert len(state["scores"]) == 2
        assert all(score >= 0 for score in state["scores"])
        assert len(state["hands"]) == 2
        assert all(len(hand) == 3 for hand in state["hands"])
        assert all(1 <= value <= 3 for hand in state["hands"] for value in hand)
