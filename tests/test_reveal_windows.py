import copy
import json
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

    def test_sabotage_display_only_is_closed_by_spell_caster(self):
        """When every revealed card is a unit, the caster closes the display.

        ``owner`` in a reveal record is the player whose hand is shown.  The
        player allowed to end a display-only reveal is that player's opponent,
        i.e. the Sabotage caster (P0 in this fixture), not the hand owner.
        """
        row = self.state["players"][0]
        card = row["main"].pop()
        self.state["cards"][card]["code"] = "OGN-156"
        row["hand"].append(card)
        opponent = self.state["players"][1]
        for uid in opponent["hand"]:
            self.state["cards"][uid]["code"] = "OGN-001"  # unit: no legal choice
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        for _ in range(2):
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(1))
        self.assertEqual(self.state["phase"], "reveal")
        self.assertEqual(self.state["reveal"]["owner"], 1)
        self.assertEqual(self.state["reveal"]["closer"], 0)
        self.assertEqual(self.state["actor"], 0)
        end_action = next(a for a in self.rules.legal_actions(self.state)
                          if a.kind == "end_reveal")
        self.assertIsNotNone(end_action)
        wrong_state = copy.deepcopy(self.state)
        wrong_state["actor"] = 1
        self.assertFalse(any(a.kind == "end_reveal" for a in self.rules.legal_actions(wrong_state)))
        with self.assertRaises(ValueError):
            self.rules.apply(wrong_state, end_action, random.Random(1))
        self.rules.apply(self.state, end_action, random.Random(1))
        self.assertIsNone(self.state["reveal"])
        self.assertTrue(self.state["chain"])
        self.assertTrue(self.state["chain"][-1].get("reveal_done"))

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

class NocturneRevealTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(7))
        self.state.update(phase="chain", actor=0, turn_player=0, turn=2)
        row = self.state["players"][0]
        card = row["main"].pop()
        self.state["cards"][card]["code"] = "OGN-194"
        row["main"].insert(0, card)
        self.card = card
        self.item = {"effect": "vision", "owner": 0, "card": None}

    def test_vision_nocturne_can_be_declined_without_revealing_to_opponent(self):
        self.rules._effect_vision(self.state, self.item, random.Random(1))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.rules.observe(self.state, 1)["decision"], None)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if json.loads(a.arguments).get("option") == "nocturne_skip")
        self.rules.apply(self.state, action, random.Random(1))
        self.assertEqual(self.state["decision"]["kind"], "predict")
        self.assertEqual(self.state["players"][0]["main"][0], self.card)

    def test_vision_nocturne_banishes_and_plays_for_rainbow_power(self):
        self.state["players"][0]["power"] = ["body"]
        self.rules._effect_vision(self.state, self.item, random.Random(1))
        action = next(a for a in self.rules.legal_actions(self.state)
                      if json.loads(a.arguments).get("option") == "nocturne_banish")
        self.rules.apply(self.state, action, random.Random(1))
        self.assertTrue(any(u["code"] == "OGN-194" for u in self.state["units"]))
        self.assertTrue(any(u.get("card") == self.card for u in self.state["units"]))
        self.assertEqual(self.state["players"][0]["power"], [])
        self.rules.validate(self.state)

    def test_vision_nocturne_banish_choice_unavailable_without_power(self):
        self.rules._effect_vision(self.state, self.item, random.Random(1))
        options = {json.loads(a.arguments).get("option") for a in self.rules.legal_actions(self.state)}
        self.assertNotIn("nocturne_banish", options)
        self.assertIn("nocturne_skip", options)
