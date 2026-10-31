import json
import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class NextBattlefieldTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(8))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)

    def unit(self, code="OGN-219", player=0, location=0):
        row = self.state["players"][player]
        card = next(uid for uid in row["main"] if self.state["cards"][uid]["code"] == code)
        row["main"].remove(card)
        unit = self.rules._new_unit(self.state, code, player, location, card=card, exhausted=False)
        self.state["fields"][location]["controller"] = player
        return unit

    def test_altar_to_unity_hold_creates_recruit(self):
        self.state["fields"][0]["code"] = "OGN-275"
        self.unit()
        before = len(self.rules._units(self.state, 0))
        self.rules._score(self.state, 0, 0, "hold", random.Random(3))
        self.assertEqual(len(self.rules._units(self.state, 0)), before + 1)
        self.assertTrue(any(u["code"] == "OGN-273" for u in self.rules._units(self.state, 0)))

    def test_navori_fighting_pit_buffs_first_unbuffed_unit(self):
        self.state["fields"][0]["code"] = "OGN-283"
        unit = self.unit()
        self.rules._score(self.state, 0, 0, "hold", random.Random(3))
        self.assertEqual(unit["buff"], 1)

    def test_navori_fighting_pit_requires_target_when_two_units_are_unbuffed(self):
        self.state["fields"][0]["code"] = "OGN-283"
        first = self.unit()
        second = self.unit()
        self.rules._score(self.state, 0, 0, "hold", random.Random(3))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["kind"], "target")
        self.assertEqual(set(self.state["decision"]["targets"]), {first["id"], second["id"]})
        self.rules.apply(self.state, Action.make("choose_target", target=second["id"]), random.Random(3))
        self.assertEqual(first["buff"], 0)
        self.assertEqual(second["buff"], 1)

    def test_monastery_of_hirana_opens_optional_buff_target_window(self):
        self.state["fields"][0]["code"] = "OGN-282"
        first = self.unit()
        second = self.unit()
        first["buff"] = 1
        second["buff"] = 1
        before_hand = len(self.state["players"][0]["hand"])
        self.rules._score(self.state, 0, 0, "conquer", random.Random(3))
        self.assertEqual(self.state["phase"], "optional")
        accept = Action.make("optional_effect", optional=self.state["optional"][0]["id"], accept=True)
        self.rules.apply(self.state, accept, random.Random(3))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["kind"], "target")
        self.assertEqual(set(self.state["decision"]["targets"]), {first["id"], second["id"]})
        self.rules.apply(self.state, Action.make("choose_target", target=second["id"]), random.Random(3))
        self.assertEqual(first["buff"], 1)
        self.assertEqual(second["buff"], 0)
        self.assertEqual(len(self.state["players"][0]["hand"]), before_hand + 1)

    def test_candlelit_sanctum_can_recycle_none_and_order_retained_cards(self):
        self.state["fields"][0]["code"] = "OGN-291"
        row = self.state["players"][0]
        top = list(row["main"][:2])
        self.rules._score(self.state, 0, 0, "conquer", random.Random(3))
        self.assertEqual(self.state["phase"], "optional")
        accept = Action.make("optional_effect", optional=self.state["optional"][0]["id"], accept=True)
        self.rules.apply(self.state, accept, random.Random(3))
        self.assertEqual(self.state["phase"], "reveal")
        self.assertEqual(self.state["reveal"]["effect"], "recycle_top_two")
        self.rules.apply(self.state, Action.make("confirm_revealed"), random.Random(3))
        self.assertEqual(self.state["reveal"]["kind"], "reorder")
        orders = [a for a in self.rules.legal_actions(self.state) if a.kind == "order_revealed"]
        self.assertEqual(len(orders), 2)
        reversed_order = next(a for a in orders if list(json.loads(a.arguments)["order"]) == list(reversed(top)))
        self.rules.apply(self.state, reversed_order, random.Random(3))
        self.assertEqual(row["main"][:2], list(reversed(top)))

    def test_void_gate_adds_bonus_spell_damage(self):
        self.state["fields"][0]["code"] = "OGN-296"
        unit = self.unit(location=0)
        self.rules._effect_spell(self.state, {"code": "OGN-009", "owner": 0,
                                              "targets": [unit["id"]], "card": "none"}, random.Random(3))
        self.assertEqual(unit["damage"], 4)


if __name__ == "__main__":
    unittest.main()
