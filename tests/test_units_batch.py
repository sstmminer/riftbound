import random
import unittest

from riftbound.origins import OriginsRules


class RemainingOriginsUnitTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(91))
        self.state.update(phase="showdown", actor=0, turn_player=0, turn=3)

    def _card(self, player, code):
        row = self.state["players"][player]
        uid = row["main"].pop()
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def test_volibear_attack_target_window_accepts_one_to_five_targets(self):
        card = self._card(0, "OGN-041")
        source = self.rules._new_unit(self.state, "OGN-041", 0, 0, card=card, exhausted=False)
        enemy = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        self.state["fields"][0]["controller"] = 1
        self.state["battle"] = {"field": 0, "attacker": 0, "combat": True,
                                 "designation_triggers_added": False}
        self.state["focus"] = 0
        self.rules._close_showdown(self.state, random.Random(2))
        self.assertTrue(self.state["decision"]["multi"])
        self.assertEqual(self.state["decision"]["min"], 5)
        self.assertEqual(self.state["decision"]["max"], 5)
        for _ in range(5):
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "choose_target"), random.Random(2))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "confirm_targets"), random.Random(2))
        self.assertEqual(self.state["phase"], "chain")
        for _ in range(2):
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "pass"), random.Random(2))
        self.assertEqual(enemy["damage"], 5)

    def test_teemo_defend_reveals_and_recycles_top_five(self):
        card = self._card(1, "OGN-121")
        source = self.rules._new_unit(self.state, "OGN-121", 1, 0, card=card, exhausted=False)
        target = self.rules._new_unit(self.state, "OGN-003", 0, 0, exhausted=False)
        row = self.state["players"][1]
        before_main = len(row["main"])
        top = list(row["main"][:5])
        for uid in top[:2]:
            self.state["cards"][uid]["code"] = "OGN-121"
        self.state["fields"][0]["controller"] = 0
        self.state["battle"] = {"field": 0, "attacker": 0, "combat": True,
                                 "designation_triggers_added": False}
        self.state["focus"] = 0
        self.rules._close_showdown(self.state, random.Random(2))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target"), random.Random(2))
        for _ in range(2):
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "pass"), random.Random(2))
        self.assertEqual(self.state["phase"], "reveal")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "end_reveal"), random.Random(2))
        for _ in range(2):
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "pass"), random.Random(2))
        self.assertEqual(target["damage"], 2)
        self.assertEqual(len(row["main"]), before_main)


    def test_kaisa_conquer_replays_low_energy_trash_spell_and_recycles(self):
        self.state.update(phase="main", actor=0, turn_player=0)
        row = self.state["players"][0]
        kaisa_card = self._card(0, "OGN-112")
        self.rules._new_unit(self.state, "OGN-112", 0, 0, card=kaisa_card, exhausted=False)
        self.state["fields"][0]["controller"] = 0
        spell = row["main"].pop()
        self.state["cards"][spell]["code"] = "OGN-005"
        row["trash"].append(spell)
        row["energy"], row["power"] = 20, ["fury"] * 3
        self.state["points"][0] = 4
        self.rules._score(self.state, 0, 0, "conquer", random.Random(7))
        accept = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "optional_effect" and '"accept":true' in a.arguments)
        self.rules.apply(self.state, accept, random.Random(7))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_revealed"), random.Random(7))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "confirm_revealed"), random.Random(7))
        while self.state["phase"] in {"chain", "decision"}:
            actions = self.rules.legal_actions(self.state)
            if self.state["phase"] == "decision":
                action = next(a for a in actions if a.kind == "choose_target")
            else:
                action = next(a for a in actions if a.kind == "pass")
            self.rules.apply(self.state, action, random.Random(7))
        self.assertIn(spell, row["main"])
        self.assertNotIn(spell, row["trash"])


if __name__ == "__main__":
    unittest.main()
