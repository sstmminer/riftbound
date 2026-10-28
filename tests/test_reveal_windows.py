import random
import unittest

from riftbound.origins import OriginsRules


class RevealWindowTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(41))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["body"] * 8

    def test_sabotage_reveals_hand_then_recycles_selected_non_unit(self):
        row = self.state["players"][0]
        card = row["main"].pop()
        self.state["cards"][card]["code"] = "OGN-156"
        row["hand"].append(card)
        opponent_card = self.state["players"][1]["hand"][0]
        self.state["cards"][opponent_card]["code"] = "OGN-201"
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        for _ in range(2):
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(1))
        self.assertEqual(self.state["phase"], "reveal")
        self.assertIn(opponent_card, self.state["reveal"]["cards"])
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "choose_revealed" and opponent_card in a.arguments),
                         random.Random(1))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "confirm_revealed"),
                         random.Random(1))
        self.assertIn(opponent_card, self.state["players"][1]["main"])
        self.rules.validate(self.state)

    def test_forge_opens_non_overlapping_trash_selection(self):
        row = self.state["players"][0]
        gear_card = row["main"].pop()
        self.state["cards"][gear_card]["code"] = "OGN-212"
        row["gear"].append({"id": gear_card, "card": gear_card, "code": "OGN-212",
                             "owner": 0, "location": "base:0", "exhausted": False})
        cards = list(row["main"][:3])
        row["trash"].extend(cards)
        del row["main"][:3]
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "gear_forge_recycle")
        self.rules.apply(self.state, action, random.Random(1))
        self.assertEqual(self.state["phase"], "reveal")
        self.assertEqual(set(self.state["reveal"]["cards"]), set(row["trash"]))
        for uid in cards[:2]:
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state)
                                  if a.kind == "choose_revealed" and uid in a.arguments),
                             random.Random(1))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "confirm_revealed"),
                         random.Random(1))
        self.assertTrue(all(uid in row["main"] for uid in cards[:2]))
        self.rules.validate(self.state)

    def test_dr_mundo_beginning_phase_opens_trash_recycle_window(self):
        row = self.state["players"][0]
        mundo_card = row["main"].pop()
        self.state["cards"][mundo_card]["code"] = "OGN-109"
        self.rules._new_unit(self.state, "OGN-109", 0, "base:0", card=mundo_card, exhausted=False)
        cards = list(row["main"][:3])
        row["trash"].extend(cards)
        del row["main"][:3]
        self.rules._start_turn(self.state, random.Random(1))
        self.assertEqual(self.state["phase"], "reveal")
        self.assertEqual(self.state["reveal"]["effect"], "dr_mundo_recycle")
        self.assertEqual(set(self.state["reveal"]["cards"]), set(row["trash"]))


if __name__ == "__main__":
    unittest.main()
