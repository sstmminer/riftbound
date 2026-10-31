import copy
import random
import unittest

from riftbound.origins import OriginsRules
from tools.contract_invariants import violations


class IndependentContractInvariantTests(unittest.TestCase):
    def test_initial_state_satisfies_independent_contract(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(7))
        self.assertEqual(violations(state), [])

    def test_legal_transitions_preserve_independent_contract(self):
        rules = OriginsRules()
        for seed in range(3):
            rng = random.Random(seed)
            state = rules.initial_state(random.Random(seed))
            for _ in range(100):
                self.assertEqual(violations(state), [])
                if state.get("winner") is not None:
                    break
                actions = tuple(rules.legal_actions(state))
                self.assertTrue(actions)
                rules.apply(state, rng.choice(actions), rng)
            self.assertEqual(violations(state), [])

    def test_duplicate_card_reference_is_rejected(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(8))
        duplicate = state["players"][0]["hand"][0]
        state["players"][0]["trash"].append(duplicate)
        self.assertIn("physical card referenced more than once", violations(state))

    def test_contract_does_not_mutate_state(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(9))
        before = copy.deepcopy(state)
        violations(state)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
