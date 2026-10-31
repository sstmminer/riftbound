import copy
import json
import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class RulesAuditRegressionTests(unittest.TestCase):
    def test_native_mistfall_uses_the_same_optional_window_as_a_copy(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(101))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        state["players"][0]["power"] = ["body"]
        target = rules._new_unit(state, "OGN-003", 0, 0, exhausted=True)
        state["players"][0]["gear"].append({
            "id": "g152", "card": None, "code": "OGN-152", "owner": 0,
            "location": "base:0", "exhausted": False,
        })
        rules._apply_buff(state, target)
        self.assertEqual(state["phase"], "optional")
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "optional_effect"
                      and '"accept":true' in action.arguments)
        rules.apply(state, action, random.Random(101))
        self.assertFalse(target["exhausted"])
        self.assertEqual(state["players"][0]["power"], [])

    def test_multiple_heimer_sources_expose_orderable_registry_event_window(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(104))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        state["players"][0]["power"] = ["body", "body", "body"]
        target = rules._new_unit(state, "OGN-003", 0, 0, exhausted=True)
        first = rules._new_unit(state, "OGN-111", 0, 0, exhausted=False)
        second = rules._new_unit(state, "OGN-111", 0, 0, exhausted=False)
        state["players"][0]["gear"].append({
            "id": "g152", "card": None, "code": "OGN-152", "owner": 0,
            "location": "base:0", "exhausted": False,
        })
        rules._apply_buff(state, target)
        self.assertEqual(len(state["optional"]), 3)
        self.assertTrue(all(item["registry_ability"] == "gear.mistfall_ready"
                            for item in state["optional"]))
        order = next(action for action in rules.legal_actions(state)
                     if action.kind == "order_optional")
        rules.apply(state, order, random.Random(104))
        self.assertEqual(state["optional_ordered"], True)
        ordered_ids = list(json.loads(order.arguments)["order"])
        self.assertEqual([item["id"] for item in state["optional"]], ordered_ids)

    def test_native_boss_death_replacement_is_optional_and_recalls(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(102))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        state["players"][0]["legend"] = "OGN-269"
        state["players"][0]["power"] = ["fury"]
        target = rules._new_unit(state, "OGN-003", 0, 0, exhausted=False)
        rules._apply_buff(state, target)
        target["damage"] = rules.might(state, target)
        rules._cleanup(state, random.Random(102))
        self.assertEqual(state["phase"], "optional")
        order = next((action for action in rules.legal_actions(state)
                      if action.kind == "order_optional"), None)
        if order is not None:
            rules.apply(state, order, random.Random(102))
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "optional_effect"
                      and '"accept":true' in action.arguments)
        rules.apply(state, action, random.Random(102))
        self.assertIn(target, state["units"])
        self.assertEqual(target["location"], "base:0")
        self.assertEqual(target["buff"], 0)
        self.assertEqual(target["damage"], 0)

    def test_invalid_copied_activation_is_state_atomic(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(103))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        heimer = rules._new_unit(state, "OGN-111", 0, "base:0", exhausted=False)
        before = copy.deepcopy(state)
        action = Action.make("ability_activate", ability_id="legend.blind_monk_buff",
                             source=heimer["id"], origin="legend:0", copied_from="OGN-257")
        with self.assertRaises(ValueError):
            rules.apply(state, action, random.Random(103))
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
