import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class BattlefieldBeginningPhaseTriggerTests(unittest.TestCase):
    def _state_with_two_hold_optionals(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(901))
        state.update(phase="main", actor=0, turn_player=0, turn=1, winner=None)
        row = state["players"][0]
        row["champion"] = []
        champion = row["main"].pop()
        state["cards"][champion]["code"] = "OGN-027"
        row["trash"].append(champion)
        for field, code in enumerate(("OGN-281", "OGN-288")):
            state["fields"][field]["code"] = code
            state["fields"][field]["controller"] = 0
            rules._new_unit(state, "OGN-219", 0, field, exhausted=False)
        return rules, state

    def test_hold_triggers_from_two_battlefields_share_one_order_window(self):
        rules, state = self._state_with_two_hold_optionals()
        rules._start_turn(state, random.Random(902))

        self.assertEqual(state["phase"], "optional")
        self.assertEqual({item["effect"] for item in state["optional"]},
                         {"return_champion", "channel_rune"})
        actions = rules.legal_actions(state)
        self.assertEqual({action.kind for action in actions}, {"order_optional"})
        self.assertEqual(len(actions), 2)

    def test_ordered_beginning_triggers_resolve_before_returning_to_main(self):
        rules, state = self._state_with_two_hold_optionals()
        rules._start_turn(state, random.Random(903))
        option_ids = {item["effect"]: item["id"] for item in state["optional"]}
        order = [option_ids["channel_rune"], option_ids["return_champion"]]
        rules.apply(state, Action.make("order_optional", order=order), random.Random(904))

        self.assertEqual(state["phase"], "optional")
        self.assertEqual(state["optional"][0]["id"], order[0])
        rules.apply(state, Action.make("optional_effect",
                                      optional=order[0], accept=True), random.Random(905))
        self.assertEqual(state["phase"], "optional")
        rules.apply(state, Action.make("optional_effect",
                                      optional=order[1], accept=True), random.Random(906))
        self.assertEqual(state["phase"], "main")
        self.assertTrue(state["players"][0]["champion"])


if __name__ == "__main__":
    unittest.main()
