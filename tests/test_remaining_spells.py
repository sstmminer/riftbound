import random
import unittest

from riftbound.origins import OriginsRules


class RemainingOriginSpellTests(unittest.TestCase):
    def scenario(self, code, *, power="fury"):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(31))
        state.update(phase="main", actor=0, turn_player=0, turn=2)
        for row in state["players"]:
            row["energy"] = 20
            row["power"] = [power] * 20
        row = state["players"][0]
        card = row["main"].pop()
        state["cards"][card]["code"] = code
        row["hand"].append(card)
        return rules, state, card

    def pass_chain(self, rules, state):
        for _ in range(2):
            action = next(action for action in rules.legal_actions(state)
                           if action.kind == "pass")
            rules.apply(state, action, random.Random(7))

    def test_blind_fury_reveals_opponent_top_and_banishes_selected(self):
        rules, state, card = self.scenario("OGN-025")
        opponent = state["players"][1]
        top = opponent["main"][0]
        state["cards"][top]["code"] = "OGN-088"
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "play_spell" and card in action.arguments)
        rules.apply(state, action, random.Random(7))
        self.pass_chain(rules, state)
        self.assertEqual(state["phase"], "reveal")
        self.assertEqual(state["reveal"]["owner"], 1)
        rules.apply(state, next(a for a in rules.legal_actions(state)
                                if a.kind == "choose_revealed"), random.Random(7))
        rules.apply(state, next(a for a in rules.legal_actions(state)
                                if a.kind == "confirm_revealed"), random.Random(7))
        self.assertNotIn(top, state["players"][1]["main"])
        self.assertTrue(any(unit["code"] == "OGN-088" and unit["owner"] == 0
                            for unit in state["units"]))
        self.assertEqual(state["cards"][top]["owner"], 1)
        played = next(unit for unit in state["units"] if unit["card"] == top)
        self.assertEqual(played["card_owner"], 1)
        played["damage"] = rules.might(state, played)
        rules._cleanup(state, random.Random(7))
        self.assertIn(top, state["players"][1]["trash"])
        self.assertNotIn(top, state["players"][0]["trash"])

    def test_blind_fury_targeted_spell_opens_click_target_window(self):
        rules, state, card = self.scenario("OGN-025")
        opponent = state["players"][1]
        top = opponent["main"][0]
        state["cards"][top]["code"] = "OGN-009"
        target = rules._new_unit(state, "OGN-001", 1, 0, card=None, exhausted=False)
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "play_spell" and card in action.arguments)
        rules.apply(state, action, random.Random(7))
        self.pass_chain(rules, state)
        rules.apply(state, next(a for a in rules.legal_actions(state)
                                if a.kind == "choose_revealed"), random.Random(7))
        rules.apply(state, next(a for a in rules.legal_actions(state)
                                if a.kind == "confirm_revealed"), random.Random(7))
        self.assertEqual(state["decision"]["kind"], "target")
        self.assertEqual(state["decision"]["targets"], [target["id"]])
        rules.apply(state, next(a for a in rules.legal_actions(state)
                                if a.kind == "choose_target"), random.Random(7))
        self.assertEqual(state["phase"], "chain")
        self.assertEqual(state["chain"][-1]["targets"], [target["id"]])

    def test_blind_fury_dangerous_duo_opens_entry_target_window(self):
        rules, state, card = self.scenario("OGN-025")
        opponent = state["players"][1]
        top = opponent["main"][0]
        state["cards"][top]["code"] = "OGN-016"
        target = rules._new_unit(state, "OGN-001", 0, "base:0", card=None, exhausted=False)
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "play_spell" and card in action.arguments)
        rules.apply(state, action, random.Random(7))
        self.pass_chain(rules, state)
        rules.apply(state, next(a for a in rules.legal_actions(state)
                                if a.kind == "choose_revealed"), random.Random(7))
        rules.apply(state, next(a for a in rules.legal_actions(state)
                                if a.kind == "confirm_revealed"), random.Random(7))
        self.assertEqual(state["decision"]["targets"], [target["id"]])
        rules.apply(state, next(a for a in rules.legal_actions(state)
                                if a.kind == "choose_target" and target["id"] in a.arguments),
                    random.Random(7))
        while state["phase"] == "chain":
            rules.apply(state, next(a for a in rules.legal_actions(state)
                                    if a.kind == "pass"), random.Random(7))
        self.assertEqual(target["temporary"], 2)

    def test_promising_future_collects_both_choices_in_next_player_order(self):
        rules, state, card = self.scenario("OGN-115", power="mind")
        for row in state["players"]:
            row["power"] = ["mind", "fury"] * 10
        top1 = state["players"][1]["main"][0]
        top0 = state["players"][0]["main"][0]
        state["cards"][top1]["code"] = "OGN-088"
        state["cards"][top0]["code"] = "OGN-009"
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "play_spell" and card in action.arguments)
        rules.apply(state, action, random.Random(7))
        self.pass_chain(rules, state)
        self.assertEqual(state["reveal"]["owner"], 1)
        for _ in range(2):
            rules.apply(state, next(a for a in rules.legal_actions(state)
                                    if a.kind == "choose_revealed"), random.Random(7))
            rules.apply(state, next(a for a in rules.legal_actions(state)
                                    if a.kind == "confirm_revealed"), random.Random(7))
        for _ in range(12):
            if state["phase"] not in {"chain", "decision"}:
                break
            actions = rules.legal_actions(state)
            if state["phase"] == "decision":
                action = next((a for a in actions
                               if a.kind == "choose_option" and '"skip"' in a.arguments), actions[0])
            else:
                action = next(a for a in actions if a.kind == "pass")
            rules.apply(state, action, random.Random(7))
        self.assertTrue(any(unit["code"] == "OGN-088" and unit["owner"] == 1
                            for unit in state["units"]))
        self.assertFalse(any(unit["code"] == "OGN-009" for unit in state["units"]))
        self.assertIn(top0, state["players"][0]["trash"])
        self.assertEqual(state["phase"], "main")

    def test_divine_judgment_opens_per_player_multi_zone_selection(self):
        rules, state, card = self.scenario("OGN-244", power="order")
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "play_spell" and card in action.arguments)
        rules.apply(state, action, random.Random(7))
        self.pass_chain(rules, state)
        self.assertEqual(state["decision"]["kind"], "divine")
        for player in (0, 1):
            decision = state["decision"]
            for zone, required in decision["required"].items():
                for value in decision["choices"][zone][:required]:
                    action = next(a for a in rules.legal_actions(state)
                                  if a.kind == "choose_divine" and zone in a.arguments and value in a.arguments)
                    rules.apply(state, action, random.Random(7))
            rules.apply(state, next(a for a in rules.legal_actions(state)
                                    if a.kind == "confirm_divine"), random.Random(7))
            if player == 0:
                self.assertEqual(state["decision"]["player"], 1)
        self.assertNotEqual(state["phase"], "decision")


if __name__ == "__main__":
    unittest.main()
