import random
import unittest

from riftbound.origins import OriginsRules


class GearBatchTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(71))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["fury", "calm", "mind", "body", "chaos", "order"] * 2

    def card(self, code):
        row = self.state["players"][0]
        uid = next(uid for uid in row["main"] if self.state["cards"][uid]["code"] == "OGN-219")
        row["main"].remove(uid)
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def play(self, code):
        uid = self.card(code)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_gear" and uid in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.rules.validate(self.state)
        return uid

    def test_gear_enters_ready_at_controller_base(self):
        uid = self.play("OGN-040")
        gear = self.state["players"][0]["gear"][-1]
        self.assertEqual((gear["card"], gear["location"], gear["exhausted"]), (uid, "base:0", False))

    def test_resource_seals_and_energy_conduit_activate(self):
        self.play("OGN-040")
        before = len(self.state["players"][0]["power"])
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "gear_resource" and '"domain":"fury"' in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.assertEqual(len(self.state["players"][0]["power"]), before + 1)
        self.play("OGN-098")
        before_energy = self.state["players"][0]["energy"]
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "gear_resource" and '"energy":1' in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.assertEqual(self.state["players"][0]["energy"], before_energy + 1)

    def test_iron_ballista_enters_exhausted(self):
        self.play("OGN-017")
        self.assertTrue(self.state["players"][0]["gear"][-1]["exhausted"])

    def test_scrapheap_play_draws_and_forge_creates_recruit(self):
        before = len(self.state["players"][0]["hand"])
        self.play("OGN-182")
        self.assertEqual(len(self.state["players"][0]["hand"]), before + 1)
        self.play("OGN-212")
        self.assertTrue(any(u["code"] == "OGN-273" and u["owner"] == 0
                            for u in self.state["units"]))

    def test_thermo_beam_kills_all_gear(self):
        gear = self.play("OGN-040")
        self.state["players"][0]["power"].append("fury")
        spell = self.card("OGN-022")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and spell in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        while self.state["phase"] == "chain":
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "pass"), random.Random(4))
        self.assertFalse(self.state["players"][0]["gear"])
        self.assertIn(gear, self.state["players"][0]["trash"])

    def test_unlicensed_armory_arms_optional_death_replacement(self):
        gear_card = self.play("OGN-023")
        target = self.rules._new_unit(self.state, "OGN-219", 0, "base:0", card=None, exhausted=False)
        self.state["phase"], self.state["actor"] = "main", 0
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "gear_targeted" and gear_card in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and target["id"] in a.arguments), random.Random(4))
        self.assertEqual(target["death_replacement"]["kind"], "armory")
        target["damage"] = self.rules.might(self.state, target)
        self.rules._cleanup(self.state, random.Random(4))
        self.assertEqual(self.state["phase"], "optional")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "optional_effect" and '"accept":true' in a.arguments), random.Random(4))
        self.assertIn(target, self.state["units"])
        self.assertEqual(target["location"], "base:0")
        self.assertTrue(target["exhausted"])
        self.assertEqual(target["damage"], 0)

    def test_zhonyas_hourglass_replaces_lethal_unit(self):
        self.play("OGN-077")
        target = self.rules._new_unit(self.state, "OGN-219", 0, "base:0", card=None, exhausted=False)
        target["damage"] = self.rules.might(self.state, target)
        self.rules._cleanup(self.state, random.Random(4))
        self.assertIn(target, self.state["units"])
        self.assertEqual(target["location"], "base:0")
        self.assertTrue(target["exhausted"])
        self.assertFalse(self.state["players"][0]["gear"])

    def test_baited_hook_opens_top_five_selection(self):
        gear_card = self.play("OGN-242")
        target = self.rules._new_unit(self.state, "OGN-219", 0, "base:0", card=None, exhausted=False)
        self.state["phase"], self.state["actor"] = "main", 0
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "gear_targeted" and gear_card in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and target["id"] in a.arguments), random.Random(4))
        self.assertEqual(self.state["phase"], "reveal")
        reveal = self.state["reveal"]
        self.assertLessEqual(len(reveal["cards"]), 5)
        self.assertEqual(reveal["effect"], "baited_hook")

    def test_dazzling_aurora_plays_first_topdeck_unit(self):
        self.play("OGN-160")
        row = self.state["players"][0]
        first, second = row["main"][:2]
        self.state["cards"][first]["code"] = "OGN-024"
        self.state["cards"][second]["code"] = "OGN-219"
        before = len(self.state["units"])
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "end_turn"), random.Random(4))
        self.assertEqual(len(self.state["units"]), before + 1)
        self.assertEqual(self.state["units"][-1]["card"], second)


if __name__ == "__main__":
    unittest.main()
