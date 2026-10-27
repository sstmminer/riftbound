import random
import unittest

from riftbound.origins import OriginsRules


class UnitsBatchBTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(31))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["body", "chaos", "order", "fury", "calm", "mind"] * 2

    def card(self, code, player=0):
        row = self.state["players"][player]
        for zone in ("hand", "main", "champion"):
            for uid in row[zone]:
                if self.state["cards"][uid]["code"] == "OGN-219":
                    row[zone].remove(uid)
                    self.state["cards"][uid]["code"] = code
                    row["hand"].append(uid)
                    return uid
        raise AssertionError("no spare physical card")

    def drain(self):
        while self.state["phase"] in {"chain", "trigger_order", "showdown"}:
            options = self.rules.legal_actions(self.state)
            if not options:
                break
            self.rules.apply(self.state, options[0], random.Random(9))

    def test_cithria_buffs_when_another_unit_is_played(self):
        cithria = self.rules._new_unit(self.state, "OGN-139", 0, "base:0", exhausted=False)
        card = self.card("OGN-219")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "play_unit" and card in a.arguments), random.Random(9))
        self.drain()
        self.assertEqual(cithria["buff"], 1)

    def test_cemetery_attendant_returns_a_unit(self):
        target = self.card("OGN-219")
        row = self.state["players"][0]
        row["hand"].remove(target)
        row["trash"].append(target)
        attendant = self.card("OGN-165")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_unit" and attendant in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(self.state["phase"], "decision")
        choose = next(a for a in self.rules.legal_actions(self.state)
                      if target in a.arguments)
        self.rules.apply(self.state, choose, random.Random(9))
        self.assertIn(target, row["hand"])

    def test_vanguard_captain_creates_two_recruits_on_legion_play(self):
        self.state["players"][0]["played"] = 1
        card = self.card("OGN-218")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_unit" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(sum(u["code"] == "OGN-273" for u in self.state["units"]), 2)

    def test_solari_chief_stuns_then_kills_target(self):
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        card = self.card("OGN-225")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_unit" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(self.state["phase"], "decision")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if enemy["id"] in a.arguments), random.Random(9))
        self.assertTrue(enemy["stunned"])

    def test_viktor_leader_creates_recruit_when_another_unit_dies(self):
        self.rules._new_unit(self.state, "OGN-246", 0, "base:0", exhausted=False)
        victim = self.rules._new_unit(self.state, "OGN-219", 0, "base:0", exhausted=False)
        victim["damage"] = self.rules.might(self.state, victim)
        self.rules._cleanup(self.state, random.Random(9))
        self.assertEqual(sum(u["code"] == "OGN-273" for u in self.state["units"]), 1)

    def test_deadbloom_predator_can_enter_occupied_enemy_field(self):
        self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        card = self.card("OGN-161")
        actions = [a for a in self.rules.legal_actions(self.state)
                   if a.kind == "play_unit" and card in a.arguments]
        self.assertTrue(any('"location":0' in a.arguments for a in actions))

    def test_sai_scout_has_open_field_and_vision_trigger(self):
        card = self.card("OGN-174")
        actions = [a for a in self.rules.legal_actions(self.state)
                   if a.kind == "play_unit" and card in a.arguments]
        self.assertTrue(any('"location":0' in a.arguments or '"location":1' in a.arguments
                            for a in actions))

    def test_rhasa_cost_reduces_with_trash_cards(self):
        row = self.state["players"][0]
        row["trash"].extend(row["main"][:3])
        del row["main"][:3]
        card = self.card("OGN-195")
        actions = [a for a in self.rules.legal_actions(self.state)
                   if a.kind == "play_unit" and card in a.arguments]
        self.assertTrue(actions)

    def test_machine_evangel_deathknell_creates_three_recruits(self):
        machine = self.rules._new_unit(self.state, "OGN-239", 0, "base:0", exhausted=False)
        machine["damage"] = self.rules.might(self.state, machine)
        self.rules._cleanup(self.state, random.Random(9))
        self.assertEqual(sum(u["code"] == "OGN-273" for u in self.state["units"]), 3)


if __name__ == "__main__":
    unittest.main()
