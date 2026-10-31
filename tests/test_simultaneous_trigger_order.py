import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class SimultaneousTriggerOrderTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(812))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)

    def test_turn_player_orders_first_then_other_player(self):
        triggers = [
            {"effect": "first_a", "owner": 0},
            {"effect": "second_a", "owner": 1},
            {"effect": "first_b", "owner": 0},
        ]
        self.rules._triggers(self.state, triggers)
        self.assertEqual(self.state["phase"], "trigger_order")
        self.assertEqual(self.state["actor"], 0)
        self.assertEqual({item["effect"] for item in self.state["pending"]},
                         {"first_a", "first_b"})

        self.rules.apply(
            self.state, Action.make("order_triggers", order=[1, 0]),
            random.Random(813),
        )
        self.assertEqual(self.state["phase"], "trigger_order")
        self.assertEqual(self.state["actor"], 1)
        self.assertEqual([item["effect"] for item in self.state["ordered_triggers"]],
                         ["first_b", "first_a"])

        self.rules.apply(
            self.state, Action.make("order_triggers", order=[0]),
            random.Random(814),
        )
        self.assertEqual(self.state["phase"], "chain")
        # Turn Player's group is added first, then the other player's group;
        # the latter is therefore the top item and resolves first.
        self.assertEqual([item["effect"] for item in self.state["chain"]],
                         ["first_b", "first_a", "second_a"])

    def test_turn_order_starts_with_player_one_when_they_are_active(self):
        self.state.update(turn_player=1, actor=1)
        triggers = [
            {"effect": "p0", "owner": 0},
            {"effect": "p1", "owner": 1},
        ]
        self.rules._triggers(self.state, triggers)
        self.assertEqual(self.state["actor"], 1)
        self.rules.apply(
            self.state, Action.make("order_triggers", order=[0]),
            random.Random(815),
        )
        self.assertEqual(self.state["actor"], 0)
        self.rules.apply(
            self.state, Action.make("order_triggers", order=[0]),
            random.Random(816),
        )
        self.assertEqual([item["owner"] for item in self.state["chain"]], [1, 0])


if __name__ == "__main__":
    unittest.main()
