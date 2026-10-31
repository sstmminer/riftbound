import json
import random
import unittest

from riftbound.origins import OriginsRules


class HiddenTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(81))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["fields"][0]["controller"] = 0
        self.state["players"][0]["energy"] = 10
        self.state["players"][0]["power"] = ["fury", "calm", "mind", "body"] * 3
        self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)

    def card(self, code):
        row = self.state["players"][0]
        uid = next(uid for uid in row["main"] if self.state["cards"][uid]["code"] == "OGN-219")
        row["main"].remove(uid)
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def test_hide_is_private_to_owner_and_uses_facedown_zone(self):
        card = self.card("OGN-053")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "hide_card" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(3))
        self.rules.validate(self.state)
        self.assertEqual(self.state["players"][0]["hidden"][0]["field"], 0)
        self.assertEqual(self.rules.observe(self.state, 0)["players"][0]["hidden"][0]["code"], "OGN-053")
        self.assertEqual(self.rules.observe(self.state, 1)["players"][0]["hidden"][0]["code"], "__back__")

    def test_hidden_stand_united_prompts_target_then_enters_chain(self):
        card = self.card("OGN-053")
        hide = next(a for a in self.rules.legal_actions(self.state) if a.kind == "hide_card" and card in a.arguments)
        self.rules.apply(self.state, hide, random.Random(3))
        self.state["turn"] = 3
        friendly = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_hidden_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(3))
        self.assertEqual(self.state["phase"], "decision")
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_target" and friendly["id"] in a.arguments)
        self.rules.apply(self.state, choose, random.Random(3))
        self.assertEqual(self.state["phase"], "chain")

    def test_hidden_tideturner_allows_friendly_target_at_another_location(self):
        card = self.card("OGN-199")
        self.state["fields"][1]["controller"] = 0
        hide = next(a for a in self.rules.legal_actions(self.state)
                    if a.kind == "hide_card" and card in a.arguments and '"field":0' in a.arguments)
        self.rules.apply(self.state, hide, random.Random(3))
        self.state["turn"] = 3
        target = self.rules._new_unit(self.state, "OGN-219", 0, 1, exhausted=False)
        play = next(a for a in self.rules.legal_actions(self.state)
                    if a.kind == "play_hidden_targeted" and card in a.arguments)
        self.rules.apply(self.state, play, random.Random(3))
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_target" and target["id"] in a.arguments)
        self.rules.apply(self.state, choose, random.Random(3))
        # The play itself creates a triggered ability whose target is chosen
        # before priority is passed (RUP5 403.2/811.1.d.3).
        choose_trigger = next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "choose_target" and target["id"] in a.arguments)
        self.rules.apply(self.state, choose_trigger, random.Random(3))
        for _ in range(2):
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(3))
        tideturner = next(u for u in self.state["units"] if u["code"] == "OGN-199")
        self.assertEqual(tideturner["location"], 1)
        self.assertEqual(target["location"], 0)

    def test_hidden_facebreaker_selects_one_friendly_and_enemy_before_chain(self):
        card = self.card("OGN-220")
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "hide_card" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(3))
        self.state["turn"] = 3
        friendly = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        second_friendly = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        play = next(a for a in self.rules.legal_actions(self.state)
                    if a.kind == "play_hidden_targeted" and card in a.arguments)
        self.rules.apply(self.state, play, random.Random(3))
        self.assertEqual(self.state["phase"], "decision")
        # Selecting two friendly units is rejected immediately; the latest
        # click cannot leave an impossible Facebreaker selection open.
        first = next(a for a in self.rules.legal_actions(self.state)
                     if a.kind == "choose_target" and friendly["id"] in a.arguments)
        self.rules.apply(self.state, first, random.Random(3))
        bad = next(a for a in self.rules.legal_actions(self.state)
                   if a.kind == "choose_target" and second_friendly["id"] in a.arguments)
        with self.assertRaises(ValueError):
            self.rules.apply(self.state, bad, random.Random(3))
        good = next(a for a in self.rules.legal_actions(self.state)
                    if a.kind == "choose_target" and enemy["id"] in a.arguments)
        self.rules.apply(self.state, good, random.Random(3))
        confirm = next(a for a in self.rules.legal_actions(self.state)
                       if a.kind == "confirm_targets")
        self.rules.apply(self.state, confirm, random.Random(3))
        self.assertEqual(self.state["phase"], "chain")
        for _ in range(2):
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "pass"), random.Random(3))
        self.assertTrue(friendly["stunned"])
        self.assertTrue(enemy["stunned"])

    def test_hidden_fox_fire_uses_multi_target_window(self):
        card = self.card("OGN-256")
        hide = next(a for a in self.rules.legal_actions(self.state)
                    if a.kind == "hide_card" and card in a.arguments)
        self.rules.apply(self.state, hide, random.Random(3))
        self.state["turn"] = 3
        first = self.rules._new_unit(self.state, "OGN-271", 1, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-271", 1, 0, exhausted=False)
        play = next(a for a in self.rules.legal_actions(self.state)
                    if a.kind == "play_hidden_targeted" and card in a.arguments)
        self.rules.apply(self.state, play, random.Random(3))
        self.assertTrue(self.state["decision"].get("multi"))
        for target in (first, second):
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "choose_target" and target["id"] in a.arguments),
                             random.Random(3))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "confirm_targets"), random.Random(3))
        self.assertEqual(self.state["phase"], "chain")


if __name__ == "__main__":
    unittest.main()
