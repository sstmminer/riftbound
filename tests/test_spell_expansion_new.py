import random
import unittest

from riftbound.origins import OriginsRules


class SpellExpansionNewTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(123))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["chaos", "order"] * 4

    def spare(self, code):
        row = self.state["players"][0]
        uid = row["main"].pop()
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def drain(self):
        for _ in range(8):
            if self.state["phase"] not in {"chain", "showdown"}:
                return
            action = next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass")
            self.rules.apply(self.state, action, random.Random(9))
        self.fail("chain did not close")

    def test_stacked_deck_selects_one_of_top_three_and_recycles_rest(self):
        card = self.spare("OGN-183")
        row = self.state["players"][0]
        top = list(row["main"][:3])
        self.assertEqual(len(top), 3)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["targets"], top)
        chosen = top[1]
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and chosen in a.arguments),
                         random.Random(9))
        self.drain()
        self.assertIn(chosen, row["hand"])
        self.assertTrue(all(uid in row["main"] for uid in top if uid != chosen))
        self.assertTrue(all(uid not in row["trash"] for uid in top))

    def test_possession_takes_control_and_recalls_without_showdown(self):
        card = self.spare("OGN-203")
        enemy_card = self.state["players"][1]["main"].pop()
        self.state["cards"][enemy_card]["code"] = "OGN-219"
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0,
                                     card=enemy_card, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and enemy["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(enemy["owner"], 0)
        self.assertEqual(enemy["card_owner"], 1)
        self.assertEqual(enemy["location"], "base:0")
        self.assertTrue(enemy["exhausted"])
        enemy["damage"] = self.rules.might(self.state, enemy)
        self.rules._cleanup(self.state, random.Random(9))
        self.assertIn(enemy_card, self.state["players"][1]["trash"])
        self.assertNotIn(enemy_card, self.state["players"][0]["trash"])
        self.assertEqual(self.state["phase"], "main")

    def test_imperial_decree_kills_unit_when_it_takes_damage(self):
        card = self.spare("OGN-221")
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertIn("imperial_decree", self.state)
        self.rules._deal_damage(self.state, target, 1)
        self.rules._cleanup(self.state, random.Random(9))
        self.assertNotIn(target, self.state["units"])

    def test_icathian_rain_allows_six_repeated_targets(self):
        card = self.spare("OGN-248")
        self.state["players"][0]["power"] = ["fury", "mind", "body"] * 2
        target = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        for _ in range(6):
            self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                              if a.kind == "choose_target" and target["id"] in a.arguments), random.Random(9))
        self.assertTrue(any(a.kind == "confirm_targets" for a in self.rules.legal_actions(self.state)))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "confirm_targets"), random.Random(9))
        self.drain()
        self.assertEqual(target["damage"], 12)

    def test_falling_star_uses_ordered_two_click_target_window(self):
        card = self.spare("OGN-029")
        self.state["players"][0]["power"] = ["fury"] * 4
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        for _ in range(2):
            self.rules.apply(
                self.state,
                next(a for a in self.rules.legal_actions(self.state)
                     if a.kind == "choose_target" and target["id"] in a.arguments),
                random.Random(9),
            )
        self.assertEqual(self.state["decision"]["selected"], [target["id"], target["id"]])
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "confirm_targets"), random.Random(9))
        self.drain()
        self.assertNotIn(target, self.state["units"])

    def test_simple_target_spell_uses_card_click_target_window(self):
        card = self.spare("OGN-169")
        target = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.assertEqual(self.state["decision"]["targets"], [target["id"]])
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and target["id"] in a.arguments),
                         random.Random(9))
        self.drain()
        self.assertNotIn(target, self.state["units"])

    def test_bullet_time_pays_two_rainbow_power_and_hits_all_enemy_units(self):
        card = self.spare("OGN-268")
        self.state["players"][0]["power"] = ["fury", "mind", "body"]
        first = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and '"x":2' in a.arguments
                      and '"destination":0' in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual((first["damage"], second["damage"]), (2, 2))


    def test_guerilla_warfare_returns_hidden_cards_and_grants_free_hide(self):
        card = self.spare("OGN-264")
        hidden = self.state["players"][0]["main"].pop()
        self.state["cards"][hidden]["code"] = "OGN-094"
        self.state["players"][0]["trash"].append(hidden)
        self.state["players"][0]["power"] = ["mind", "chaos"] * 4
        self.rules._new_unit(self.state, "OGN-003", 0, 0, exhausted=False)
        self.state["fields"][0]["controller"] = 0
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(self.state["phase"], "reveal")
        self.assertIn(hidden, self.state["reveal"]["choices"])
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_revealed" and hidden in a.arguments),
                         random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "confirm_revealed"), random.Random(9))
        self.drain()
        row = self.state["players"][0]
        self.assertIn(hidden, row["hand"])
        self.assertTrue(row["free_hide_turn"])
        hide = next(a for a in self.rules.legal_actions(self.state)
                    if a.kind == "hide_card" and hidden in a.arguments and '"ignore_cost":true' in a.arguments)
        self.rules.apply(self.state, hide, random.Random(9))
        self.assertTrue(any(h["id"] == hidden for h in row["hidden"]))
        self.rules.validate(self.state)


    def test_get_excited_discards_then_targets_and_uses_discarded_energy(self):
        card = self.spare("OGN-008")
        discard = self.state["players"][0]["main"].pop()
        self.state["cards"][discard]["code"] = "OGN-003"  # Energy 2
        self.state["players"][0]["hand"].append(discard)
        self.state["players"][0]["power"] = ["fury"] * 4
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and target["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(self.state["phase"], "decision")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "discard_card" and discard in a.arguments), random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and target["id"] in a.arguments), random.Random(9))
        self.drain()
        self.assertEqual(target["damage"], 2)
        self.assertIn(discard, self.state["players"][0]["trash"])

    def test_get_excited_targeted_gui_path_discards_before_target_choice(self):
        card = self.spare("OGN-008")
        discard = self.state["players"][0]["main"].pop()
        self.state["cards"][discard]["code"] = "OGN-003"
        self.state["players"][0]["hand"].append(discard)
        self.state["players"][0]["power"] = ["fury"] * 4
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.assertEqual(self.state["decision"]["kind"], "discard")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "discard_card" and discard in a.arguments), random.Random(9))
        self.assertEqual(self.state["decision"]["kind"], "target")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and target["id"] in a.arguments), random.Random(9))
        self.drain()
        self.assertEqual(target["damage"], 2)

    def test_fight_or_flight_uses_field_target_click(self):
        card = self.spare("OGN-168")
        self.state["players"][0]["power"] = ["fury"] * 4
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and target["id"] in a.arguments), random.Random(9))
        self.drain()
        self.assertEqual(target["location"], "base:1")

    def test_fading_memories_can_click_a_gear_target(self):
        card = self.spare("OGN-180")
        row = self.state["players"][0]
        row["energy"], row["power"] = 10, ["chaos"] * 4
        gear = row["main"].pop()
        self.state["cards"][gear]["code"] = "OGN-017"
        row["gear"].append({"id": gear, "card": gear, "code": "OGN-017",
                             "owner": 0, "card_owner": 0, "location": "base:0",
                             "exhausted": False, "temporary": False})
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell_targeted" and card in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "choose_target" and gear in a.arguments), random.Random(9))
        self.drain()
        self.assertTrue(next(item for item in row["gear"] if item["id"] == gear)["temporary"])

    def test_temporary_gear_is_removed_at_controller_beginning(self):
        row = self.state["players"][0]
        gear = row["main"].pop()
        self.state["cards"][gear]["code"] = "OGN-017"
        row["gear"].append({"id": gear, "card": gear, "code": "OGN-017",
                             "owner": 0, "card_owner": 0, "location": "base:0",
                             "exhausted": False, "temporary": True})
        self.state["turn_player"] = 0
        self.rules._start_turn(self.state, random.Random(9))
        self.assertNotIn(gear, [item["id"] for item in row["gear"]])
        self.assertIn(gear, row["trash"])

    def test_block_grants_shield_three_and_temporary_tank(self):
        card = self.spare("OGN-057")
        self.state["players"][0]["power"] = ["calm"] * 4
        target = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and target["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(target["combat_shield"], 3)
        self.assertTrue(target["temporary_tank"])


    def test_stormbringer_damages_field_then_moves_base_unit(self):
        card = self.spare("OGN-250")
        self.state["players"][0]["power"] = ["fury", "body"] * 4
        source = self.rules._new_unit(self.state, "OGN-219", 0, "base:0", exhausted=False)
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments
                      and source["id"] in a.arguments and '"destination":0' in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(source["location"], 0)
        self.assertTrue(source["exhausted"])
        self.assertGreaterEqual(enemy["damage"], 3)

    def test_fox_fire_kills_selected_units_with_might_budget(self):
        card = self.spare("OGN-256")
        self.state["players"][0]["power"] = ["calm", "mind"] * 4
        first = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-003", 1, 0, exhausted=False)
        actions = [a for a in self.rules.legal_actions(self.state)
                   if a.kind == "play_spell" and card in a.arguments
                   and first["id"] in a.arguments and second["id"] in a.arguments]
        self.assertTrue(actions)
        self.rules.apply(self.state, actions[0], random.Random(9))
        self.drain()
        self.assertNotIn(first, self.state["units"])
        self.assertNotIn(second, self.state["units"])



if __name__ == "__main__":
    unittest.main()
