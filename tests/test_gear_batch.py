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

    def drain_aurora(self):
        """Let the opposing player close each public reveal and drain its chain."""
        for _ in range(20):
            if self.state["phase"] == "reveal":
                action = next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "end_reveal")
            elif self.state["phase"] == "chain":
                action = next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "pass")
            else:
                return
            self.rules.apply(self.state, action, random.Random(4))

    def finish_aurora(self, expected_card=None):
        """Drive Aurora's public reveal and ordinary continuation chain."""
        for _ in range(40):
            if expected_card is not None and any(unit.get("card") == expected_card
                                                  for unit in self.state["units"]):
                return
            phase = self.state["phase"]
            if phase == "reveal":
                action = next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "end_reveal")
            elif phase == "chain":
                action = next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "pass")
            elif phase == "decision":
                actions = self.rules.legal_actions(self.state)
                action = next((a for a in actions if '"option":"nocturne_skip"' in a.arguments), actions[0])
            elif phase == "optional":
                action = next(a for a in self.rules.legal_actions(self.state)
                              if '"accept":false' in a.arguments)
            else:
                return
            self.rules.apply(self.state, action, random.Random(4))
        self.fail("Aurora continuation did not settle")

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

    def test_optional_armory_can_be_declined_before_zhonya_fallback(self):
        row = self.state["players"][0]
        row["gear"].append({"id": "z", "card": None, "code": "OGN-077",
                             "owner": 0, "location": "base:0", "exhausted": False})
        unit = self.rules._new_unit(self.state, "OGN-219", 0, "base:0",
                                    card=None, exhausted=False)
        unit["death_replacement"] = {"kind": "armory", "turn": self.state["turn"]}
        row["power"] = ["fury"]
        unit["damage"] = self.rules.might(self.state, unit)
        self.rules._cleanup(self.state, random.Random(4))
        self.assertEqual(self.state["phase"], "optional")
        decline = next(a for a in self.rules.legal_actions(self.state)
                       if a.kind == "optional_effect" and '"accept":false' in a.arguments)
        self.rules.apply(self.state, decline, random.Random(4))
        self.assertIn(unit, self.state["units"])
        self.assertEqual(unit["location"], "base:0")
        self.assertTrue(unit["exhausted"])
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

    def test_baited_hook_uses_normal_free_play_and_entry_target(self):
        gear_card = self.play("OGN-242")
        killed = self.rules._new_unit(self.state, "OGN-219", 0, "base:0", card=None, exhausted=False)
        entry_target = self.rules._new_unit(self.state, "OGN-001", 0, "base:0", card=None, exhausted=False)
        row = self.state["players"][0]
        top = row["main"][0]
        self.state["cards"][top]["code"] = "OGN-016"
        self.state["phase"], self.state["actor"] = "main", 0
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "gear_targeted" and gear_card in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and killed["id"] in a.arguments),
                         random.Random(4))
        self.assertTrue(any(a.kind == "choose_revealed" and top in a.arguments
                            for a in self.rules.legal_actions(self.state)))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_revealed" and top in a.arguments),
                         random.Random(4))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "confirm_revealed"), random.Random(4))
        self.assertEqual(self.state["decision"]["targets"], [entry_target["id"]])
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and entry_target["id"] in a.arguments),
                         random.Random(4))
        self.assertTrue(any(unit["code"] == "OGN-016" and unit["owner"] == 0
                            for unit in self.state["units"]))

    def test_dazzling_aurora_plays_first_topdeck_unit(self):
        self.play("OGN-160")
        row = self.state["players"][0]
        first, second = row["main"][:2]
        self.state["cards"][first]["code"] = "OGN-024"
        self.state["cards"][second]["code"] = "OGN-219"
        before = len(self.state["units"])
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "end_turn"), random.Random(4))
        self.finish_aurora(second)
        self.assertEqual(len(self.state["units"]), before + 1)
        self.assertEqual(self.state["units"][-1]["card"], second)

    def test_dazzling_aurora_uses_normal_free_play_entry_target_window(self):
        self.play("OGN-160")
        row = self.state["players"][0]
        top = row["main"][0]
        self.state["cards"][top]["code"] = "OGN-016"
        target = self.rules._new_unit(self.state, "OGN-001", 0, "base:0",
                                      card=None, exhausted=False)
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "end_turn"), random.Random(4))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "end_reveal"), random.Random(4))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["targets"], [target["id"]])
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target"), random.Random(4))
        self.finish_aurora(top)
        self.assertTrue(any(unit.get("card") == top for unit in self.state["units"]))

    def test_dazzling_aurora_pauses_for_nocturne_replacement(self):
        self.play("OGN-160")
        row = self.state["players"][0]
        nocturne, unit = row["main"][:2]
        self.state["cards"][nocturne]["code"] = "OGN-194"
        self.state["cards"][unit]["code"] = "OGN-219"
        row["power"] = ["body"]
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "end_turn"), random.Random(4))
        self.assertEqual(self.state["phase"], "decision")
        self.assertTrue(any("nocturne_banish" in a.arguments
                            for a in self.rules.legal_actions(self.state)))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if "nocturne_skip" in a.arguments), random.Random(4))
        self.finish_aurora(nocturne)
        self.assertTrue(any(u.get("card") == nocturne for u in self.state["units"]))

    def test_dazzling_aurora_nocturne_can_banish_then_continue(self):
        self.play("OGN-160")
        row = self.state["players"][0]
        nocturne, unit = row["main"][:2]
        self.state["cards"][nocturne]["code"] = "OGN-194"
        self.state["cards"][unit]["code"] = "OGN-219"
        row["power"] = ["body"]
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "end_turn"), random.Random(4))
        banish = next(a for a in self.rules.legal_actions(self.state)
                      if "nocturne_banish" in a.arguments)
        self.rules.apply(self.state, banish, random.Random(4))
        self.assertTrue(any("nocturne_leave" in a.arguments
                            for a in self.rules.legal_actions(self.state)))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if "nocturne_leave" in a.arguments), random.Random(4))
        self.assertIn(nocturne, row["banishment"])
        self.finish_aurora(unit)
        self.assertTrue(any(u.get("card") == unit for u in self.state["units"]))


if __name__ == "__main__":
    unittest.main()
