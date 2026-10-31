import json
import random
import unittest

from riftbound.origins import OriginsRules


class UnverifiedOriginsCardsTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(17))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        for row in self.state["players"]:
            row["energy"] = 20
            row["power"] = ["chaos", "order", "body", "mind"] * 3

    def _kill(self, unit):
        unit["damage"] = self.rules.might(self.state, unit)
        self.rules._cleanup(self.state, random.Random(19))

    def test_wraith_draws_once_per_source_each_turn(self):
        wraith = self.rules._new_unit(self.state, "OGN-118", 0, "base:0", exhausted=False)
        first = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        before = len(self.state["players"][0]["hand"])
        self._kill(first)
        self.assertEqual(len(self.state["players"][0]["hand"]), before + 1)
        second = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        before = len(self.state["players"][0]["hand"])
        self._kill(second)
        self.assertEqual(len(self.state["players"][0]["hand"]), before)
        self.assertEqual(wraith.get("wraith_draw_turn"), self.state["turn"])

    def test_undercover_deathknell_opens_manual_discard_then_draws(self):
        undercover = self.rules._new_unit(self.state, "OGN-178", 0, 0, exhausted=False)
        before_hand = len(self.state["players"][0]["hand"])
        self._kill(undercover)
        self.assertEqual(self.state["phase"], "decision")
        self.assertTrue(self.state["decision"]["undercover_discard"])
        chosen = []
        for _ in range(2):
            action = next(a for a in self.rules.legal_actions(self.state)
                          if a.kind == "discard_card" and a.arguments not in chosen)
            chosen.append(action.arguments)
            self.rules.apply(self.state, action, random.Random(19))
        self.assertEqual(self.state["phase"], "main")
        self.assertIsNone(self.state["decision"])
        self.assertEqual(len(self.state["players"][0]["hand"]), before_hand)

    def test_mindsplitter_reveals_then_caster_selects_opponent_card(self):
        row = self.state["players"][0]
        card = row["main"].pop()
        self.state["cards"][card]["code"] = "OGN-192"
        row["hand"].append(card)
        opponent_row = self.state["players"][1]
        chosen = opponent_row["main"].pop()
        self.state["cards"][chosen]["code"] = "OGN-005"
        opponent_row["hand"].append(chosen)
        play = next(action for action in self.rules.legal_actions(self.state)
                    if action.kind == "play_unit" and card in action.arguments)
        self.rules.apply(self.state, play, random.Random(19))
        while self.state["phase"] == "chain":
            self.rules.apply(self.state,
                             next(action for action in self.rules.legal_actions(self.state)
                                  if action.kind == "pass"), random.Random(19))
        self.assertEqual(self.state["phase"], "reveal")
        reveal_choice = next(action for action in self.rules.legal_actions(self.state)
                             if action.kind == "choose_revealed"
                             and json.loads(action.arguments)["card"] == chosen)
        self.rules.apply(self.state, reveal_choice, random.Random(19))
        self.rules.apply(self.state,
                         next(action for action in self.rules.legal_actions(self.state)
                              if action.kind == "confirm_revealed"), random.Random(19))
        self.assertIn(chosen, opponent_row["trash"])
        self.assertNotIn(chosen, opponent_row["hand"])

    def test_spirits_refuge_entry_targets_and_grants_deflect(self):
        row = self.state["players"][0]
        row["power"] = ["calm"] * 8
        unit = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        card = row["main"].pop()
        self.state["cards"][card]["code"] = "OGN-063"
        row["hand"].append(card)
        action = next(action for action in self.rules.legal_actions(self.state)
                      if action.kind == "play_gear" and card in action.arguments)
        self.rules.apply(self.state, action, random.Random(19))
        while self.state["phase"] in {"decision", "chain"}:
            actions = self.rules.legal_actions(self.state)
            target_action = next((action for action in actions
                                  if action.kind == "choose_target"
                                  and json.loads(action.arguments)["target"] == unit["id"]), None)
            self.rules.apply(self.state, target_action or
                             next(action for action in actions if action.kind == "pass"),
                             random.Random(19))
        self.assertEqual(unit["buff"], 1)
        self.assertEqual(self.rules._deflect(self.state, unit), 1)

    def test_ready_helper_applies_pirates_haven_bonus(self):
        row = self.state["players"][0]
        row["gear"].append({"id": "gear:143", "card": None, "code": "OGN-143",
                             "owner": 0, "card_owner": 0, "location": "base:0",
                             "exhausted": False, "temporary": False})
        unit = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=True)
        self.assertTrue(self.rules._ready_unit(self.state, unit))
        self.assertFalse(unit["exhausted"])
        self.assertEqual(unit["temporary"], 1)

    def test_miss_fortune_first_move_opens_optional_ready_target(self):
        self.state["fields"][0]["controller"] = 0
        self.state["fields"][1]["controller"] = 0
        source = self.rules._new_unit(
            self.state, "OGN-162", 0, 0, exhausted=False)
        target = self.rules._new_unit(
            self.state, "OGN-219", 0, 0, exhausted=True)
        self.rules._resolve_move(
            self.state, [source], 1, 0, random.Random(19))
        self.assertEqual(self.state["phase"], "optional")
        accept = next(action for action in self.rules.legal_actions(self.state)
                      if '"accept":true' in action.arguments)
        self.rules.apply(self.state, accept, random.Random(19))
        choose = next(action for action in self.rules.legal_actions(self.state)
                      if action.kind == "choose_target"
                      and target["id"] in action.arguments)
        self.rules.apply(self.state, choose, random.Random(19))
        self.assertFalse(target["exhausted"])
        self.assertEqual(source["move_count"], 1)

    def test_vanguard_helm_death_opens_another_unit_target(self):
        self.state["fields"][0]["controller"] = 0
        self.state["players"][0]["gear"].append(
            {"id": "gear:228", "card": None, "code": "OGN-228",
             "owner": 0, "card_owner": 0, "location": "base:0",
             "exhausted": False, "temporary": False})
        victim = self.rules._new_unit(
            self.state, "OGN-219", 0, 0, exhausted=False)
        target = self.rules._new_unit(
            self.state, "OGN-219", 0, 0, exhausted=False)
        victim["buff"] = 1
        victim["damage"] = self.rules.might(self.state, victim)
        self.rules._cleanup(self.state, random.Random(19))
        choose = next(action for action in self.rules.legal_actions(self.state)
                      if action.kind == "choose_target"
                      and target["id"] in action.arguments)
        self.rules.apply(self.state, choose, random.Random(19))
        for _ in range(2):
            self.rules.apply(
                self.state,
                next(action for action in self.rules.legal_actions(self.state)
                     if action.kind == "pass"),
                random.Random(19),
            )
        self.assertEqual(target["buff"], 1)


if __name__ == "__main__":
    unittest.main()
