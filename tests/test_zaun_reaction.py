import json
import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class ZaunAndHeimerReactionTests(unittest.TestCase):
    def test_zaun_warrens_lets_controller_choose_discard_and_returns_to_main(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(101))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        state["fields"][0]["code"] = "OGN-298"
        row = state["players"][0]
        chosen = row["hand"][-1]
        before_main = len(row["main"])

        rules._score(state, 0, 0, "conquer", random.Random(102))
        self.assertEqual(state["decision"]["kind"], "discard")
        actions = rules.legal_actions(state)
        discard_actions = [action for action in actions if action.kind == "discard_card"]
        self.assertEqual({json.loads(action.arguments)["card"] for action in discard_actions},
                         set(row["hand"]))

        chosen_action = next(action for action in discard_actions
                             if json.loads(action.arguments)["card"] == chosen)
        rules.apply(state, chosen_action, random.Random(103))

        self.assertIn(chosen, row["trash"])
        self.assertNotIn(chosen, row["hand"])
        self.assertEqual(len(row["main"]), before_main - 1)
        self.assertIsNone(state["decision"])
        self.assertEqual(state["phase"], "main")
        self.assertEqual(state["actor"], state["turn_player"])

    def test_heimer_reaction_copies_are_hidden_in_main_but_open_in_chain(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(104))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        state["players"][0]["legend"] = "OGN-247"  # Daughter of the Void
        heimer = rules._new_unit(state, "OGN-111", 0, 0, exhausted=False)
        state["players"][0]["gear"].append({
            "id": "gear:040", "card": None, "code": "OGN-040", "owner": 0,
            "location": "base:0", "exhausted": False,
        })

        def copied_ids():
            return {
                json.loads(action.arguments)["ability_id"]
                for action in rules.legal_actions(state)
                if action.kind in {"ability_activate", "ability_targeted"}
                and json.loads(action.arguments).get("source") == heimer["id"]
            }

        self.assertNotIn("legend.daughter_spell_power", copied_ids())
        self.assertNotIn("gear.seal_of_rage_resource", copied_ids())

        state["phase"] = "chain"
        self.assertIn("legend.daughter_spell_power", copied_ids())
        self.assertIn("gear.seal_of_rage_resource", copied_ids())

    def test_heimer_reaction_copy_rejects_direct_main_phase_activation(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(105))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        state["players"][0]["legend"] = "OGN-247"
        heimer = rules._new_unit(state, "OGN-111", 0, 0, exhausted=False)
        action = Action.make("ability_activate", ability_id="legend.daughter_spell_power",
                             source=heimer["id"], origin="legend:0",
                             copied_from="OGN-247")
        with self.assertRaisesRegex(ValueError, "outside a reaction window"):
            rules.apply(state, action, random.Random(106))


if __name__ == "__main__":
    unittest.main()
