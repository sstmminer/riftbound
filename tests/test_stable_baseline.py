import unittest

from riftbound.engine import Action, Environment
from riftbound.origins import OriginsRules
from tools.stable_baseline import _semantic_digest, run_game


class _NoActionRules:
    """Tiny backend that enters a nonterminal state with no legal action."""

    id = "test-no-action-rules-v1"

    def initial_state(self, rng):
        return {"phase": "start"}

    def player(self, state):
        return 0

    def legal_actions(self, state):
        return (Action.make("stuck"),) if state["phase"] == "start" else ()

    def observe(self, state, player):
        return {"player": player, "phase": state["phase"]}

    def apply(self, state, action, rng):
        if action != Action.make("stuck") or state["phase"] != "start":
            raise ValueError("invalid test action")
        state["phase"] = "stuck"

    def outcome(self, state):
        return None

    def validate(self, state):
        if state.get("phase") not in {"start", "stuck"}:
            raise ValueError("invalid test phase")


class _TwoStateCycleRules:
    """Backend with legal reversible transitions but no terminal outcome."""

    id = "test-two-state-cycle-v1"

    def initial_state(self, rng):
        return {"phase": "a"}

    def player(self, state):
        return 0

    def legal_actions(self, state):
        return (Action.make("toggle"),)

    def observe(self, state, player):
        return {"player": player, "phase": state["phase"]}

    def apply(self, state, action, rng):
        if action != Action.make("toggle"):
            raise ValueError("invalid test action")
        state["phase"] = "b" if state["phase"] == "a" else "a"

    def outcome(self, state):
        return None

    def validate(self, state):
        if state.get("phase") not in {"a", "b"}:
            raise ValueError("invalid test phase")


class StableBaselineTests(unittest.TestCase):
    def test_semantic_digest_ignores_rng_and_allocation_counter(self):
        env = Environment(OriginsRules())
        env.reset(seed=0)
        first = _semantic_digest(env)
        env._rng.random()
        env._state["next_object"] += 17
        self.assertEqual(first, _semantic_digest(env))

    def test_truncated_game_still_replays_and_is_reported(self):
        result = run_game(OriginsRules(), "greedy", seed=0, max_steps=1)
        self.assertTrue(result["truncated"])
        self.assertFalse(result["terminated"])
        self.assertFalse(result["deadlock"])
        self.assertTrue(result["replay_verified"])
        self.assertNotIn("failure", result)

    def test_nonterminal_empty_actions_are_reported_as_deadlock(self):
        result = run_game(_NoActionRules(), "random", seed=0, max_steps=10)
        self.assertTrue(result["deadlock"])
        self.assertFalse(result["terminated"])
        self.assertFalse(result["truncated"])
        self.assertFalse(result["replay_verified"])
        self.assertIn("nonterminal state needs valid legal actions", result["failure"])

    def test_reversible_cycle_is_caught_by_step_cap(self):
        result = run_game(_TwoStateCycleRules(), "random", seed=0, max_steps=6)
        self.assertFalse(result["deadlock"])
        self.assertFalse(result["terminated"])
        self.assertTrue(result["truncated"])
        self.assertTrue(result["replay_verified"])
        self.assertGreater(result["repeated_states"], 0)
        self.assertNotIn("failure", result)


if __name__ == "__main__":
    unittest.main()
