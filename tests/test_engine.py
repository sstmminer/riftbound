import copy
import unittest

from riftbound.engine import Action, Environment, InvalidAction, RulesUnavailable, replay
from riftbound.training import RandomPolicy, self_play
from tests.fixture_rules import FixtureRules


class EngineTests(unittest.TestCase):
    def make_env(self, **kwargs):
        env = Environment(FixtureRules(), **kwargs)
        env.reset(seed=11)
        return env

    def test_official_backend_cannot_silently_fall_back(self):
        with self.assertRaises(RulesUnavailable):
            Environment()

    def test_same_seed_same_actions_same_trace(self):
        first, second = self.make_env(), self.make_env()
        while not first.done:
            action = first.legal_actions()[0]
            self.assertEqual(first.step(action), second.step(action))
        self.assertEqual(first.audit_replay(), second.audit_replay())
        self.assertTrue(first.terminated)
        self.assertFalse(first.truncated)
        self.assertEqual(sum(first.rewards), 0)

    def test_reset_restarts_rng_and_history(self):
        env = self.make_env()
        initial = env.audit_replay()
        env.step(env.legal_actions()[0])
        env.reset(seed=11)
        self.assertEqual(env.audit_replay(), initial)

    def test_invalid_actions_do_not_consume_state_or_rng(self):
        env = self.make_env()
        before = env.audit_replay()
        for action in (Action.make("collect", slot=999), Action.make("pass")):
            with self.assertRaises(InvalidAction):
                env.step(action)
            self.assertEqual(env.audit_replay(), before)

    def test_backend_failure_is_atomic(self):
        class Broken(FixtureRules):
            def apply(self, state, action, rng):
                super().apply(state, action, rng)
                raise RuntimeError("unsupported mechanic")

        env = Environment(Broken())
        env.reset(seed=11)
        before = env.audit_replay()
        with self.assertRaisesRegex(RuntimeError, "unsupported mechanic"):
            env.step(env.legal_actions()[0])
        self.assertEqual(env.audit_replay(), before)
        self.assertEqual(env.observe(0), self.make_env().observe(0))

    def test_cloning_branches_state_and_rng_independently(self):
        env = self.make_env()
        clone = env.clone()
        before = env.audit_replay()
        action = clone.legal_actions()[0]
        result = clone.step(action)
        self.assertEqual(env.audit_replay(), before)
        self.assertEqual(env.step(action), result)
        self.assertEqual(env.audit_replay(), clone.audit_replay())

    def test_observation_is_detached(self):
        env = self.make_env()
        before = env.observe(0)
        mutated = env.observe(0)
        mutated["hand"].clear()
        mutated["scores"][0] = 99
        self.assertEqual(env.observe(0), before)

    def test_opponent_private_information_does_not_change_observation(self):
        class OtherHand(FixtureRules):
            def initial_state(self, rng):
                state = super().initial_state(rng)
                state["hands"][1] = [1, 1, 1]
                return state

        original, changed = self.make_env(), Environment(OtherHand())
        changed.reset(seed=11)
        self.assertEqual(original.observe(0), changed.observe(0))
        self.assertEqual(original.legal_actions(), changed.legal_actions())
        self.assertNotEqual(original.observe(1), changed.observe(1))

    def test_step_cap_is_truncation_not_draw(self):
        env = self.make_env(max_steps=1)
        result = env.step(env.legal_actions()[0])
        self.assertTrue(result.truncated)
        self.assertFalse(result.terminated)
        self.assertEqual(result.rewards, (0, 0))
        self.assertEqual(env.legal_actions(), ())
        with self.assertRaises(InvalidAction):
            env.step(Action.make("collect", slot=0))

    def test_finished_game_rejects_further_actions(self):
        env = self.make_env()
        while not env.done:
            env.step(env.legal_actions()[0])
        with self.assertRaises(InvalidAction):
            env.step(Action.make("collect", slot=0))

    def test_replay_round_trip_and_tampering(self):
        env = self.make_env()
        for _ in range(3):
            env.step(env.legal_actions()[0])
        record = env.audit_replay()
        self.assertEqual(replay(FixtureRules(), record).audit_replay(), record)
        bad = copy.deepcopy(record)
        bad["digests"][2] = "tampered"
        with self.assertRaisesRegex(ValueError, "step 2"):
            replay(FixtureRules(), bad)
        bad = copy.deepcopy(record)
        bad["rules_id"] = "different"
        with self.assertRaisesRegex(ValueError, "incompatible"):
            replay(FixtureRules(), bad)
        bad = copy.deepcopy(record)
        bad["events"][0]["after"]["phase"] = "tampered"
        with self.assertRaisesRegex(ValueError, "event log"):
            replay(FixtureRules(), bad)

    def test_event_log_captures_public_state_transitions_and_replays(self):
        env = self.make_env()
        env.step(env.legal_actions()[0])
        events = env.event_log
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["seq"], 1)
        self.assertEqual(events[0]["action"]["kind"], "collect")
        self.assertIn("phase", events[0]["before"])
        self.assertIn("phase", events[0]["after"])
        self.assertEqual(replay(FixtureRules(), env.audit_replay()).event_log, events)

    def test_action_canonicalization_and_round_trip(self):
        first = Action("play", '{"b":2,"a":1}')
        self.assertEqual(first, Action("play", '{"a":1,"b":2}'))
        self.assertEqual(Action.from_dict(first.to_dict()), first)
        for arguments in ("[]", "null", "1"):
            with self.assertRaises(ValueError):
                Action("play", arguments)

    def test_self_play_many_seeds_finishes_and_replays(self):
        for seed in range(100):
            env = Environment(FixtureRules())
            episode = self_play(env, (RandomPolicy(seed), RandomPolicy(seed+1)), seed=seed)
            self.assertTrue(episode.terminated)
            self.assertFalse(episode.truncated)
            self.assertIn(episode.rewards, ((1, -1), (-1, 1)))
            self.assertTrue(episode.decisions)
            for decision in episode.decisions:
                self.assertEqual(decision["player"], decision["observation"]["player"])
                self.assertIn(decision["action"], decision["legal_actions"])
                self.assertNotIn("seed", decision)
            self.assertEqual(replay(FixtureRules(), env.audit_replay()).rewards,
                             episode.rewards)


if __name__ == "__main__":
    unittest.main()
