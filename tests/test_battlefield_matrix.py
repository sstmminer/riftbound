import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class BattlefieldInteractionMatrixTests(unittest.TestCase):
    """Regression coverage for battlefield windows that pause a showdown.

    These scenarios intentionally exercise the public decision state rather
    than calling effect helpers with a preselected target.  That keeps the
    certification evidence aligned with the GUI's target-selection contract.
    """

    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(601))
        self.state.update(phase="showdown", actor=0, turn_player=0, turn=2)

    def unit(self, code, player, location=0):
        return self.rules._new_unit(
            self.state, code, player, location, card=None, exhausted=False)

    def test_fortified_position_opens_defender_target_window(self):
        self.state["fields"][0]["code"] = "OGN-279"
        self.state["fields"][0]["controller"] = 1
        attacker = self.unit("OGN-219", 0)
        defender = self.unit("OGN-219", 1)
        self.state["battle"] = {"field": 0, "attacker": 0, "combat": True}

        self.rules._close_showdown(self.state, random.Random(602))

        decision = self.state["decision"]
        self.assertEqual(decision["kind"], "target")
        self.assertEqual(decision["player"], 1)
        self.assertEqual(decision["targets"], [defender["id"]])
        self.assertNotIn(attacker["id"], decision["targets"])

        self.rules.apply(
            self.state, Action.make("choose_target", target=defender["id"]),
            random.Random(603),
        )
        self.assertEqual(defender["combat_shield"], 2)

    def test_reavers_row_accept_then_selects_one_of_multiple_friendly_units(self):
        self.state["fields"][0]["code"] = "OGN-285"
        self.state["fields"][0]["controller"] = 1
        self.unit("OGN-219", 0)
        first = self.unit("OGN-219", 1)
        second = self.unit("OGN-219", 1)
        self.state["battle"] = {"field": 0, "attacker": 0, "combat": True}

        self.rules._close_showdown(self.state, random.Random(604))
        self.assertEqual(self.state["phase"], "optional")
        optional = self.state["optional"][0]
        self.assertEqual(optional["effect"], "reaver_recall")

        self.rules.apply(
            self.state,
            Action.make("optional_effect", optional=optional["id"], accept=True),
            random.Random(605),
        )
        self.assertEqual(self.state["decision"]["kind"], "target")
        self.assertEqual(
            set(self.state["decision"]["targets"]), {first["id"], second["id"]}
        )

        self.rules.apply(
            self.state, Action.make("choose_target", target=second["id"]),
            random.Random(606),
        )
        self.assertEqual(second["location"], "base:1")
        self.assertEqual(first["location"], 0)

    def test_dreaming_tree_draws_when_target_is_killed_by_spell(self):
        self.state["fields"][0]["code"] = "OGN-292"
        target = self.unit("OGN-006", 0)
        row = self.state["players"][0]
        before = len(row["hand"])

        # Hextech Ray deals 3, which is lethal to OGN-001.  The Tree trigger
        # belongs to target selection and must survive the later cleanup.
        self.rules._effect_spell(
            self.state,
            {"code": "OGN-009", "owner": 0,
             "targets": [target["id"]], "card": "none"},
            random.Random(607),
        )

        self.assertEqual(len(row["hand"]), before + 1)
        self.assertNotIn(target["id"], {unit["id"] for unit in self.state["units"]})
        self.assertTrue(self.state["dreaming_tree_used"][0])


if __name__ == "__main__":
    unittest.main()
