import random
import unittest

from riftbound.origins import OriginsRules


class TargetWindowMigrationTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(71))
        self.state.update(phase="main", actor=0, turn_player=0, turn=3)
        for row in self.state["players"]:
            row["energy"] = 20
            row["power"] = ["fury", "mind", "body", "order"]

    def spare(self, code):
        row = self.state["players"][0]
        uid = row["main"].pop()
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def test_simple_damage_spell_exposes_click_target_decision(self):
        card = self.spare("OGN-005")
        target = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["targets"], [target["id"]])
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_target" and target["id"] in a.arguments)
        self.rules.apply(self.state, choose, random.Random(9))
        self.assertEqual(self.state["phase"], "chain")

    def test_gear_targeted_ability_opens_click_target_decision(self):
        row = self.state["players"][0]
        gear_card = row["main"].pop()
        self.state["cards"][gear_card]["code"] = "OGN-090"
        row["gear"].append({"id": gear_card, "card": gear_card, "code": "OGN-090",
                             "owner": 0, "location": "base:0", "exhausted": False})
        target = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "gear_targeted" and gear_card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["targets"], [target["id"]])
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_target" and target["id"] in a.arguments)
        self.rules.apply(self.state, choose, random.Random(9))
        self.assertEqual(target["temporary"], -1)

    def test_caitlyn_ability_exposes_click_target_decision(self):
        source = self.rules._new_unit(self.state, "OGN-068", 0, 0, exhausted=False)
        target = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "unit_ability_targeted" and source["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_target" and target["id"] in a.arguments)
        self.rules.apply(self.state, choose, random.Random(9))
        self.assertTrue(source["exhausted"])
        self.assertGreater(target["damage"], 0)

    def test_pair_spell_exposes_ordered_click_targets(self):
        card = self.spare("OGN-128")
        friendly = self.rules._new_unit(self.state, "OGN-003", 0, 0, exhausted=False)
        enemy = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.assertTrue(self.state["decision"].get("ordered_pairs"))
        for target in (friendly, enemy):
            choose = next(a for a in self.rules.legal_actions(self.state)
                          if a.kind == "choose_target" and target["id"] in a.arguments)
            self.rules.apply(self.state, choose, random.Random(9))
        self.assertEqual(self.state["decision"]["selected"], [friendly["id"], enemy["id"]])
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "confirm_targets"), random.Random(9))

    def test_destination_spell_chooses_unit_then_destination(self):
        card = self.spare("OGN-173")
        self.state["players"][0]["power"].append("chaos")
        friendly = self.rules._new_unit(self.state, "OGN-003", 0, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and friendly["id"] in a.arguments),
                         random.Random(9))
        destinations = [a for a in self.rules.legal_actions(self.state) if a.kind == "choose_option"]
        self.assertTrue(destinations)
        self.rules.apply(self.state, destinations[0], random.Random(9))
        self.assertEqual(self.state["phase"], "chain")

    def test_constrained_multi_spell_uses_click_sequence(self):
        card = self.spare("OGN-256")
        first = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        for target in (first, second):
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "choose_target" and target["id"] in a.arguments),
                             random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "confirm_targets"), random.Random(9))
        self.assertEqual(self.state["phase"], "chain")

    def test_battlefield_spell_exposes_field_click_decision(self):
        card = self.spare("OGN-266")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_field_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.assertEqual(self.state["decision"]["kind"], "field")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_field" and '"field":0' in a.arguments),
                         random.Random(9))
        self.assertEqual(self.state["phase"], "chain")

    def test_bullet_time_uses_field_click_then_x_choice(self):
        card = self.spare("OGN-268")
        target = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_field_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_field" and '"field":0' in a.arguments),
                         random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_option" and '"option":2' in a.arguments),
                         random.Random(9))
        self.assertEqual(self.state["phase"], "chain")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "pass"), random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "pass"), random.Random(9))
        self.assertEqual(target["damage"], 2)

    def test_legend_move_uses_target_then_destination_clicks(self):
        row = self.state["players"][0]
        row["legend"] = "OGN-259"
        row["energy"] = 2
        target = self.rules._new_unit(self.state, "OGN-003", 0, "base:0", exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "legend_move_targeted")
        self.rules.apply(self.state, action, random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and target["id"] in a.arguments),
                         random.Random(9))
        destination = next(a for a in self.rules.legal_actions(self.state)
                           if a.kind == "choose_option" and '"option":0' in a.arguments)
        self.rules.apply(self.state, destination, random.Random(9))
        self.assertEqual(target["location"], 0)

    def test_dragons_rage_uses_first_target_destination_then_second_target(self):
        card = self.spare("OGN-258")
        first = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-003", 1, 1, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and first["id"] in a.arguments),
                         random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_option" and '"option":1' in a.arguments),
                         random.Random(9))
        self.assertEqual(self.state["phase"], "chain")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "pass"), random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "pass"), random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and second["id"] in a.arguments),
                         random.Random(9))

    def test_twisted_fate_recycles_top_rune_and_targets_fury_damage(self):
        source = self.rules._new_unit(self.state, "OGN-200", 0, 0, exhausted=False)
        target = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        self.state["players"][0]["rune_deck"][0]["code"] = "OGN-007"
        item = {"effect": "twisted_fate", "owner": 0, "source": source["id"]}
        self.state["chain_return"] = "main"
        self.assertFalse(self.rules._effect_twisted_fate(self.state, item, random.Random(9)))
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_target" and target["id"] in a.arguments)
        self.rules.apply(self.state, choose, random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "pass"), random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "pass"), random.Random(9))
        self.assertEqual(target["damage"], 2)


if __name__ == "__main__":
    unittest.main()
