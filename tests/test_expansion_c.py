import random
import unittest

from riftbound.origins import OriginsRules


class ExpansionBatchCTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(61))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["fury", "mind", "calm", "body", "chaos"] * 3

    def spare(self, code):
        row = self.state["players"][0]
        uid = next(uid for uid in row["main"] if self.state["cards"][uid]["code"] == "OGN-219")
        row["main"].remove(uid)
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def play_unit(self, card, location="base:0"):
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_unit" and card in a.arguments and location in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))

    def drain(self):
        for _ in range(30):
            if self.state["phase"] not in {"chain", "trigger_order"}:
                return
            action = next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass")
            self.rules.apply(self.state, action, random.Random(9))
        self.fail("chain did not close")

    def choose_and_drain(self, target):
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "choose_target" and target in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()

    def test_poro_herder_buffs_and_draws_when_poro_is_controlled(self):
        self.rules._new_unit(self.state, "OGN-013", 0, "base:0", exhausted=False)
        card = self.spare("OGN-061")
        before = len(self.state["players"][0]["hand"])
        self.play_unit(card)
        source = next(unit for unit in self.state["units"] if unit["card"] == card)
        self.drain()
        self.assertEqual(source["buff"], 1)
        self.assertEqual(len(self.state["players"][0]["hand"]), before)

    def test_riptide_rex_target_is_chosen_before_priority(self):
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        card = self.spare("OGN-092")
        self.play_unit(card)
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["targets"], [enemy["id"]])
        self.choose_and_drain(enemy["id"])
        self.assertEqual(enemy["damage"], 6)

    def test_blastcone_fae_target_is_chosen_before_priority(self):
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        card = self.spare("OGN-097")
        self.play_unit(card)
        self.assertEqual(self.state["phase"], "decision")
        self.choose_and_drain(enemy["id"])
        self.assertEqual(enemy["temporary"], -2)

    def test_sprite_mother_and_sprite_call_create_temporary_ready_tokens(self):
        card = self.spare("OGN-106")
        self.play_unit(card)
        self.drain()
        self.assertTrue(any(unit["code"] == "OGN-273" and unit["temporary_unit"]
                            and not unit["exhausted"] for unit in self.state["units"]))

        spell = self.spare("OGN-094")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "play_spell" and spell in a.arguments),
                         random.Random(9))
        self.drain()
        self.assertGreaterEqual(sum(unit["code"] == "OGN-273" and unit["temporary_unit"]
                                    for unit in self.state["units"]), 2)

    def test_thousand_tailed_watcher_debuffs_all_enemy_units(self):
        first = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-219", 1, "base:1", exhausted=False)
        card = self.spare("OGN-116")
        self.play_unit(card)
        self.drain()
        self.assertEqual((first["temporary"], second["temporary"]), (-3, -3))

    def test_zaunite_bouncer_returns_selected_field_unit(self):
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        card = self.spare("OGN-188")
        self.play_unit(card)
        self.assertEqual(self.state["phase"], "decision")
        self.choose_and_drain(enemy["id"])
        self.assertNotIn(enemy, self.state["units"])

    def test_maddened_marauder_moves_selected_unit_to_its_base(self):
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        card = self.spare("OGN-191")
        self.play_unit(card)
        self.assertEqual(self.state["phase"], "decision")
        self.choose_and_drain(enemy["id"])
        self.assertEqual(enemy["location"], "base:1")
        self.assertTrue(enemy["exhausted"])


if __name__ == "__main__":
    unittest.main()
