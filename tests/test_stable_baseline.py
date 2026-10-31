import unittest

from riftbound.engine import Environment
from riftbound.origins import OriginsRules
from tools.stable_baseline import _semantic_digest, run_game


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


if __name__ == "__main__":
    unittest.main()
