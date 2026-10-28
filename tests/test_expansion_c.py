import json
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
                      if a.kind == "play_unit" and card in a.arguments and str(location) in a.arguments)
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
        self.assertTrue(any(unit["code"] == "OGN-274" and unit["temporary_unit"]
                            and not unit["exhausted"] for unit in self.state["units"]))

        spell = self.spare("OGN-094")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "play_spell" and spell in a.arguments),
                         random.Random(9))
        self.drain()
        self.assertGreaterEqual(sum(unit["code"] == "OGN-274" and unit["temporary_unit"]
                                    for unit in self.state["units"]), 2)

    def test_qiyana_conquer_requires_optional_choice(self):
        qiyana = self.rules._new_unit(self.state, "OGN-155", 0, 0, exhausted=False)
        self.state["fields"][0]["controller"] = 0
        self.rules._score(self.state, 0, 0, "conquer", random.Random(9))
        self.assertEqual(self.state["phase"], "optional")
        optional = self.state["optional"][0]
        self.assertEqual(optional["effect"], "qiyana_conquer")
        accept = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "optional_effect" and '"accept":true' in a.arguments)
        self.rules.apply(self.state, accept, random.Random(9))
        self.assertEqual(self.state["phase"], "decision")
        options = {json.loads(a.arguments)["option"] for a in self.rules.legal_actions(self.state)}
        self.assertEqual(options, {"draw", "channel"})
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if '"option":"channel"' in a.arguments), random.Random(9))
        self.assertIsNone(self.state["decision"])
        self.assertGreaterEqual(len(self.state["players"][0]["runes"]), 1)
        self.rules.validate(self.state)


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

    def test_yasuo_attack_trigger_chooses_target_before_combat_damage(self):
        attacker = self.rules._new_unit(self.state, "OGN-076", 0, 0, exhausted=False)
        defender = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        self.state.update(phase="showdown", actor=0, focus=0, passes=0,
                          battle={"field": 0, "attacker": 0, "combat": True})
        self.rules._close_showdown(self.state, random.Random(9))
        self.assertEqual(self.state["phase"], "decision")
        self.choose_and_drain(defender["id"])
        self.assertNotIn(defender, self.state["units"])

    def test_fight_or_flight_moves_a_field_unit_to_base(self):
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        card = self.spare("OGN-168")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and enemy["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(enemy["location"], "base:1")
        self.assertTrue(enemy["exhausted"])

    def test_fading_memories_marks_a_field_unit_temporary(self):
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        card = self.spare("OGN-180")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and enemy["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertTrue(enemy["temporary_unit"])

    def test_kogmaw_deathknell_damages_every_unit_at_its_field(self):
        kog = self.rules._new_unit(self.state, "OGN-190", 0, 0, exhausted=False)
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        kog["damage"] = self.rules.might(self.state, kog)
        self.rules._cleanup(self.state, random.Random(9))
        self.assertNotIn(kog, self.state["units"])
        self.assertEqual(enemy["damage"], 4)

    def test_viktor_innovator_triggers_when_playing_on_opponent_turn(self):
        self.state["turn_player"] = 1
        self.state["actor"] = 0
        self.rules._new_unit(self.state, "OGN-117", 0, "base:0", exhausted=False)
        card = self.spare("OGN-219")
        self.play_unit(card)
        self.drain()
        self.assertTrue(any(unit["code"] == "OGN-273" and unit["owner"] == 0
                            for unit in self.state["units"]))

    def test_miss_fortune_buccaneer_allows_open_battlefield_play(self):
        card = self.spare("OGN-193")
        self.assertTrue(any(a.kind == "play_unit" and card in a.arguments and '"location":0' in a.arguments
                            for a in self.rules.legal_actions(self.state)))
        self.play_unit(card, location=0)
        other = self.spare("OGN-219")
        self.assertTrue(any(a.kind == "play_unit" and other in a.arguments and '"location":1' in a.arguments
                            for a in self.rules.legal_actions(self.state)))

    def test_kadregrin_draws_for_each_mighty_unit(self):
        self.rules._new_unit(self.state, "OGN-219", 0, "base:0", exhausted=False)
        card = self.spare("OGN-038")
        before = len(self.state["players"][0]["hand"])
        self.play_unit(card)
        self.drain()
        self.assertEqual(len(self.state["players"][0]["hand"]), before)

    def test_portal_rescue_replays_a_friendly_unit_to_base(self):
        target = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        card = self.spare("OGN-102")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and target["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        rescued = [u for u in self.state["units"] if u["code"] == "OGN-219" and u["owner"] == 0]
        self.assertTrue(rescued)
        self.assertEqual(rescued[-1]["location"], "base:0")

    def test_tasty_faefolk_deathknell_channels_two_and_draws(self):
        unit = self.rules._new_unit(self.state, "OGN-075", 0, 0, exhausted=False)
        unit["damage"] = self.rules.might(self.state, unit)
        before_runes = len(self.state["players"][0]["runes"])
        self.rules._cleanup(self.state, random.Random(9))
        self.assertEqual(len(self.state["players"][0]["runes"]), before_runes + 2)

    def test_ekko_deathknell_recycles_it_and_readies_runes(self):
        card = self.spare("OGN-110")
        self.state["players"][0]["hand"].remove(card)
        unit = self.rules._new_unit(self.state, "OGN-110", 0, 0, card=card, exhausted=False)
        self.state["players"][0]["runes"] = [{"id": "x", "code": "OGN-007", "exhausted": True}]
        self.state["players"][0]["rune_deck"] = [{"id": f"d{i}", "code": "OGN-007", "exhausted": False}
                                                     for i in range(11)]
        unit["damage"] = self.rules.might(self.state, unit)
        self.rules._cleanup(self.state, random.Random(9))
        self.assertIn(card, self.state["players"][0]["main"])
        self.assertFalse(self.state["players"][0]["runes"][0]["exhausted"])

    def test_spoils_of_war_draws_two(self):
        card = self.spare("OGN-144")
        before = len(self.state["players"][0]["hand"])
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "play_spell" and card in a.arguments),
                         random.Random(9))
        self.drain()
        self.assertEqual(len(self.state["players"][0]["hand"]), before + 1)

    def test_convergent_mutation_raises_one_unit_to_another_might(self):
        first = self.rules._new_unit(self.state, "OGN-219", 0, "base:0", exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-038", 0, "base:0", exhausted=False)
        card = self.spare("OGN-108")
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments
                      and first["id"] in a.arguments and second["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(9))
        self.drain()
        self.assertEqual(self.rules.might(self.state, first), self.rules.might(self.state, second))

    def test_unyielding_spirit_prevents_spell_damage(self):
        card = self.spare("OGN-145")
        self.rules.apply(self.state, next(a for a in self.rules.legal_actions(self.state)
                                          if a.kind == "play_spell" and card in a.arguments),
                         random.Random(9))
        self.drain()
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        self.rules._deal_damage(self.state, target, 5)
        self.assertEqual(target["damage"], 0)

    def test_snapvine_fight_requires_an_enemy_target(self):
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        card = self.spare("OGN-149")
        self.play_unit(card)
        self.assertEqual(self.state["phase"], "decision")
        self.choose_and_drain(enemy["id"])
        self.assertGreater(enemy["damage"], 0)

    def test_volibear_imposing_draws_when_opponent_enters_other_field(self):
        self.rules._new_unit(self.state, "OGN-158", 0, "base:0", exhausted=False)
        enemy = self.rules._new_unit(self.state, "OGN-219", 1, "base:1", exhausted=False)
        before = len(self.state["players"][0]["hand"])
        self.rules._resolve_move(self.state, [enemy], 0, 1, random.Random(9))
        self.assertEqual(len(self.state["players"][0]["hand"]), before + 1)

    def test_kayn_ignores_damage_after_two_moves(self):
        kayn = self.rules._new_unit(self.state, "OGN-189", 0, "base:0", exhausted=False)
        self.rules._resolve_move(self.state, [kayn], 0, 0, random.Random(9))
        kayn["exhausted"] = False
        self.rules._resolve_move(self.state, [kayn], "base:0", 0, random.Random(9))
        before = kayn["damage"]
        self.rules._deal_damage(self.state, kayn, 5)
        self.assertEqual(kayn["damage"], before)


if __name__ == "__main__":
    unittest.main()
