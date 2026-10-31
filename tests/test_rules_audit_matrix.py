import copy
import random
import unittest

from riftbound.origins import OriginsRules


class RulesAuditMatrixTests(unittest.TestCase):
    """Small executable audit matrix for rule-state invariants.

    This is deliberately backend-only: it checks that every legal transition
    remains serializable, validates, and preserves detached private views.
    It is a smoke differential against the rule contract, not a second rules
    implementation.
    """

    def test_random_legal_transitions_preserve_invariants(self):
        rules = OriginsRules()
        for seed in range(5):
            rng = random.Random(seed)
            state = rules.initial_state(random.Random(seed))
            rules.validate(copy.deepcopy(state))
            for _ in range(120):
                if state.get("winner") is not None:
                    break
                actions = tuple(rules.legal_actions(state))
                self.assertTrue(actions, (seed, state["phase"], state["actor"]))
                self.assertEqual(len(actions), len(set(actions)))
                action = rng.choice(actions)
                rules.apply(state, action, rng)
                rules.validate(copy.deepcopy(state))
                first = rules.observe(state, 0)
                second = rules.observe(state, 1)
                self.assertIsNot(first, second)
                # Observations are detached and may not mutate backend state.
                first_copy = copy.deepcopy(first)
                first_copy.setdefault("hand", []).clear()
                self.assertEqual(rules.observe(state, 0), first)

    def test_public_reveal_is_shared_but_private_look_is_not(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(41))
        state.update(phase="chain", actor=0, turn_player=0, turn=2)
        top = state["players"][0]["main"][0]
        state["cards"][top]["code"] = "OGN-194"
        item = {"effect": "vision", "owner": 0, "card": None}
        rules._effect_vision(state, item, random.Random(1))
        self.assertEqual(rules.observe(state, 1)["reveal"], None)
        self.assertIsNone(rules.observe(state, 1)["decision"])
        # A public reveal exposes the card even while its owner decides how
        # to handle Nocturne's replacement.
        state["decision"] = None
        rules._open_reveal(state, owner=0, cards=[top], mode="display",
                           chooser=1, closer=1, effect="dazzling_aurora",
                           item={"effect": "dazzling_aurora_continue", "owner": 0},
                           rng=random.Random(1))
        self.assertEqual(rules.observe(state, 1)["reveal"]["cards"][0]["code"], "OGN-194")


if __name__ == "__main__":
    unittest.main()
