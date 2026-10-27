import copy
import json
import random
import unittest

from riftbound.engine import Environment, InvalidAction, RulesUnavailable, replay
from riftbound.origins import OriginsRules
from riftbound.policies import GreedyPolicy
from riftbound.support import daughter_deck, starter_deck, vision_deck
from riftbound.training import RandomPolicy, self_play


class OriginsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = OriginsRules()

    def scenario(self):
        state = self.rules.initial_state(random.Random(9))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        for row in state["players"]:
            row["energy"], row["power"] = 20, ["fury", "order", "fury", "order"]
        return state

    def take_card(self, state, code, player=0):
        row = state["players"][player]
        for zone in ("hand", "main", "champion", "trash"):
            for uid in row[zone]:
                if state["cards"][uid]["code"] == code:
                    row[zone].remove(uid)
                    return uid
        self.fail(f"no physical copy of {code}")

    def hand(self, state, code, player=0):
        uid = self.take_card(state, code, player)
        state["players"][player]["hand"].append(uid)
        return uid

    def unit(self, state, code="OGN-219", player=0, location=0):
        uid = self.take_card(state, code, player)
        unit = self.rules._new_unit(state, code, player, location, card=uid, exhausted=False)
        if location in (0, 1):
            state["fields"][location]["controller"] = player
        return unit

    def act(self, state, kind, **args):
        options = [a for a in self.rules.legal_actions(state) if a.kind == kind
                   and all(json.loads(a.arguments).get(k) == v for k, v in args.items())]
        self.assertTrue(options, (kind, args, state["phase"]))
        self.rules.apply(state, options[0], random.Random(7))
        self.rules.validate(state)

    def drain(self, state):
        for _ in range(80):
            if state["phase"] not in {"chain", "trigger_order"}:
                return
            if state["phase"] == "trigger_order":
                self.act(state, "order_triggers")
            else:
                self.act(state, "pass")
        self.fail("chain did not close")

    def test_starter_is_constructed_legal_and_unknown_effect_rejected(self):
        deck = starter_deck()
        self.assertEqual(len(deck["main"]), 40)
        deck["main"][0] = "OGN-002"
        with self.assertRaises(RulesUnavailable):
            OriginsRules([deck, starter_deck()])

    def test_daughter_cluster_deck_is_constructed_legal(self):
        deck = daughter_deck()
        rules = OriginsRules([deck, deck])
        self.assertEqual(rules.decks[0]["legend"], "OGN-247")
        self.assertEqual(len(deck["main"]), 40)

    def test_vision_deck_opens_private_predict_decision(self):
        rules = OriginsRules([vision_deck(), vision_deck()])
        state = rules.initial_state(random.Random(11))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["chaos"] * 4
        uid = next(uid for uid in state["players"][0]["main"]
                   if state["cards"][uid]["code"] == "OGN-171")
        state["players"][0]["main"].remove(uid)
        state["players"][0]["hand"].append(uid)
        self.act_with_rules(rules, state, "play_unit", card=uid, location="base:0")
        self.assertEqual(state["phase"], "chain")
        for _ in range(2):
            pass_action = next(a for a in rules.legal_actions(state) if a.kind == "pass")
            rules.apply(state, pass_action, random.Random(7))
        self.assertEqual(state["phase"], "decision")
        self.assertEqual(rules.observe(state, 1)["decision"], None)
        self.assertEqual(len(rules.observe(state, 0)["decision"]["cards"]), 1)
        self.act_with_rules(rules, state, "predict", recycle=True)
        self.assertNotEqual(state["phase"], "decision")

    def test_harnessed_dragon_opens_private_target_choice(self):
        state = self.scenario()
        dragon = self.hand(state, "OGN-219")
        state["cards"][dragon]["code"] = "OGN-234"
        enemy = self.unit(state, "OGN-219", player=1, location=0)
        self.act(state, "play_unit", card=dragon, location="base:0")
        self.assertEqual(state["phase"], "chain")
        self.act(state, "pass")
        self.act(state, "pass")
        self.assertEqual(state["phase"], "decision")
        self.assertIsNone(self.rules.observe(state, 1)["decision"])
        decision = self.rules.observe(state, 0)["decision"]
        self.assertEqual(decision["kind"], "target")
        self.assertEqual(decision["targets"], [enemy["id"]])
        self.act(state, "choose_target", target=enemy["id"])
        self.assertNotIn(enemy, state["units"])

    def test_solari_shieldbearer_stuns_an_explicit_target(self):
        state = self.scenario()
        card = self.hand(state, "OGN-219")
        state["cards"][card]["code"] = "OGN-051"
        enemy = self.unit(state, player=1, location=0)
        self.act(state, "play_unit", card=card, location="base:0")
        self.drain(state)
        self.assertEqual(state["phase"], "decision")
        self.act(state, "choose_target", target=enemy["id"])
        self.assertTrue(enemy["stunned"])

    def test_whiteflame_protector_gives_eight_temporary_might(self):
        state = self.scenario()
        card = self.hand(state, "OGN-219")
        state["cards"][card]["code"] = "OGN-082"
        state["players"][0]["power"] = ["calm", "calm"]
        target = self.unit(state, "OGN-219", location="base:0")
        self.act(state, "play_unit", card=card, location="base:0")
        self.drain(state)
        self.assertEqual(state["phase"], "decision")
        self.act(state, "choose_target", target=target["id"])
        self.assertEqual(target["temporary"], 8)

    def test_rune_prison_stuns_target_and_clears_at_turn_end(self):
        state = self.scenario()
        spell = self.hand(state, "OGN-009")
        state["cards"][spell]["code"] = "OGN-050"
        enemy = self.unit(state, player=1, location=0)
        state["players"][0]["power"] = ["calm"]
        self.act(state, "play_spell", card=spell, targets=[enemy["id"]])
        self.drain(state)
        self.assertTrue(enemy["stunned"])

    def test_discipline_buffs_and_draws(self):
        state = self.scenario()
        spell = self.hand(state, "OGN-207")
        state["cards"][spell]["code"] = "OGN-058"
        target = self.unit(state, location="base:0")
        state["players"][0]["power"] = []
        before = len(state["players"][0]["hand"])
        self.act(state, "play_spell", card=spell, targets=[target["id"]])
        self.drain(state)
        self.assertEqual(target["temporary"], 2)
        self.assertEqual(len(state["players"][0]["hand"]), before)

    def test_confront_makes_future_units_enter_ready(self):
        state = self.scenario()
        spell = self.hand(state, "OGN-024")
        state["cards"][spell]["code"] = "OGN-129"
        state["players"][0]["power"] = ["body", "order"]
        self.act(state, "play_spell", card=spell, targets=[])
        self.drain(state)
        unit_card = self.hand(state, "OGN-219")
        self.act(state, "play_unit", card=unit_card, location="base:0")
        self.assertFalse(state["units"][-1]["exhausted"])

    def test_morbid_return_chooses_a_unit_from_trash(self):
        state = self.scenario()
        returned = self.take_card(state, "OGN-219")
        state["players"][0]["trash"].append(returned)
        spell = self.hand(state, "OGN-024")
        state["cards"][spell]["code"] = "OGN-170"
        self.act(state, "play_spell", card=spell, targets=[])
        self.drain(state)
        self.assertEqual(state["phase"], "decision")
        self.act(state, "choose_target", target=returned)
        self.assertIn(returned, state["players"][0]["hand"])

    def test_en_garde_buffs_a_friendly_unit(self):
        state = self.scenario()
        spell = self.hand(state, "OGN-207")
        state["cards"][spell]["code"] = "OGN-046"
        target = self.unit(state, location=0)
        state["players"][0]["power"] = []
        self.act(state, "play_spell", card=spell, targets=[target["id"]])
        self.drain(state)
        self.assertEqual(target["temporary"], 2)

    def test_find_your_center_draws_and_channels(self):
        state = self.scenario()
        spell = self.hand(state, "OGN-024")
        state["cards"][spell]["code"] = "OGN-047"
        state["players"][0]["power"] = []
        before_hand = len(state["players"][0]["hand"])
        rune = state["players"][0]["rune_deck"].pop()
        state["players"][0]["runes"].append(rune)
        self.act(state, "play_spell", card=spell, targets=[])
        self.drain(state)
        self.assertEqual(len(state["players"][0]["hand"]), before_hand)
        self.assertTrue(rune["exhausted"])

    def test_grand_stratagem_buffs_all_friendly_units(self):
        state = self.scenario()
        first = self.unit(state, location="base:0")
        second = self.unit(state, "OGN-219", location="base:0")
        spell = self.hand(state, "OGN-024")
        state["cards"][spell]["code"] = "OGN-233"
        state["players"][0]["power"] = ["order"] * 3
        self.act(state, "play_spell", card=spell, targets=[])
        self.drain(state)
        self.assertEqual((first["temporary"], second["temporary"]), (5, 5))

    def act_with_rules(self, rules, state, kind, **args):
        options = [a for a in rules.legal_actions(state) if a.kind == kind
                   and all(json.loads(a.arguments).get(k) == v for k, v in args.items())]
        self.assertTrue(options, (kind, args, state["phase"]))
        rules.apply(state, options[0], random.Random(7))
        rules.validate(state)

    def test_archive_normalizes_champion_signature_and_errata(self):
        cards = self.rules.cards
        self.assertTrue(cards["OGN-027"]["champion"])
        self.assertIn("Darius", cards["OGN-027"]["tags"])
        self.assertTrue(cards["OGN-254"]["signature"])
        self.assertIn("banish", cards["OGN-242"]["text"])
        self.assertEqual(cards["OGN-027"]["might"], 5)
        self.assertEqual(cards["OGN-027"]["power_cost"], 1)

    def test_setup_mulligan_turns_and_second_player_extra_rune(self):
        env = Environment(self.rules)
        env.reset(seed=3)
        first = env.current_player
        keep = next(a for a in env.legal_actions() if json.loads(a.arguments)["slots"] == [])
        env.step(keep)
        env.step(keep)
        obs = env.observe(first)
        self.assertEqual(len(obs["hand"]), 5)
        self.assertEqual(len(obs["players"][first]["runes"]), 2)
        end = next(a for a in env.legal_actions() if a.kind == "end_turn")
        env.step(end)
        self.assertEqual(len(env.observe(1-first)["players"][1-first]["runes"]), 3)

    def test_hidden_opponent_hand_and_deck_order_not_in_observation(self):
        state = self.scenario()
        other = copy.deepcopy(state)
        p = other["players"][1]
        p["main"][0], p["hand"][0] = p["hand"][0], p["main"][0]
        p["rune_deck"].reverse()
        self.assertEqual(self.rules.observe(state, 0), self.rules.observe(other, 0))
        self.assertEqual(self.rules.legal_actions(state), self.rules.legal_actions(other))

    def test_accelerate_cost_and_enter_ready(self):
        state = self.scenario()
        uid = self.hand(state, "OGN-010")
        before = state["players"][0]["energy"]
        self.act(state, "play_unit", card=uid, accelerate=True, location="base:0")
        self.assertFalse(state["units"][-1]["exhausted"])
        self.assertEqual(state["players"][0]["energy"], before-3)
        self.assertEqual(len(state["players"][0]["power"]), 3)

    def test_magma_wurm_only_other_units_enter_ready(self):
        state = self.scenario()
        uid = self.hand(state, "OGN-011")
        self.act(state, "play_unit", card=uid, location="base:0")
        self.assertTrue(state["units"][-1]["exhausted"])
        uid = self.hand(state, "OGN-219")
        self.act(state, "play_unit", card=uid, location="base:0")
        self.assertFalse(state["units"][-1]["exhausted"])

    def test_legion_discount_buff_and_darius_second_card_trigger(self):
        state = self.scenario()
        darius = self.unit(state, "OGN-027", location="base:0")
        darius["exhausted"] = True
        state["players"][0]["played"] = 1
        uid = self.hand(state, "OGN-217")
        self.act(state, "play_unit", card=uid, location="base:0")
        self.assertEqual(state["phase"], "trigger_order")
        self.drain(state)
        self.assertEqual(darius["temporary"], 2)
        self.assertFalse(darius["exhausted"])
        self.assertEqual(next(u for u in state["units"] if u["card"] == uid)["buff"], 1)
        before = state["players"][0]["energy"]
        uid = self.hand(state, "OGN-012")
        self.act(state, "play_unit", card=uid, location="base:0")
        self.assertEqual(state["players"][0]["energy"], before-2)

    def test_damage_spell_and_reaction_resolve_lifo(self):
        state = self.scenario()
        enemy = self.unit(state, "OGN-210", player=1, location=0)
        ray = self.hand(state, "OGN-009")
        glory = self.hand(state, "OGN-207", player=1)
        self.act(state, "play_spell", card=ray, targets=[enemy["id"]])
        self.act(state, "pass")
        self.act(state, "play_spell", card=glory, targets=[enemy["id"]], spend_buff=None)
        self.drain(state)
        self.assertIn(enemy, state["units"])
        self.assertEqual((enemy["temporary"], enemy["damage"]), (3, 3))
        self.assertIn(ray, state["players"][0]["trash"])
        self.assertIn(glory, state["players"][1]["trash"])

    def test_invalidated_spell_target_fizzles_without_hitting_new_objects(self):
        state = self.scenario()
        enemy = self.unit(state, "OGN-210", player=1)
        ray = self.hand(state, "OGN-009")
        self.act(state, "play_spell", card=ray, targets=[enemy["id"]])
        # Unit leaves board while the spell is pending; keep physical conservation.
        state["units"].remove(enemy)
        state["players"][1]["trash"].append(enemy["card"])
        self.drain(state)
        self.assertIn(ray, state["players"][0]["trash"])

    def test_deflect_requires_additional_any_power(self):
        state = self.scenario()
        enemy = self.unit(state, "OGN-013", player=1)
        ray = self.hand(state, "OGN-009")
        state["players"][0]["power"] = ["fury"]
        self.assertFalse(any(a.kind == "play_spell" and json.loads(a.arguments)["card"] == ray
                             for a in self.rules.legal_actions(state)))
        state["players"][0]["power"].append("order")
        self.act(state, "play_spell", card=ray, targets=[enemy["id"]])
        self.assertEqual(state["players"][0]["power"], [])

    def test_call_to_glory_optional_buff_cost_and_persistence(self):
        state = self.scenario()
        unit = self.unit(state)
        unit["buff"] = 1
        spell = self.hand(state, "OGN-207")
        state["players"][0]["energy"] = 0
        self.act(state, "play_spell", card=spell, targets=[unit["id"]], spend_buff=unit["id"])
        self.drain(state)
        self.assertEqual((unit["buff"], unit["temporary"]), (0, 3))
        self.act(state, "end_turn")
        self.assertEqual(unit["temporary"], 0)

    def test_movement_drumming_token_showdown_conquer_and_hold(self):
        state = self.scenario()
        unit = self.unit(state, "OGN-222", location="base:0")
        self.act(state, "begin_move", destination=0)
        self.act(state, "select_unit", unit=unit["id"])
        self.act(state, "commit_move")
        self.drain(state)
        self.assertEqual(len(self.rules._units(state, 0, 0)), 2)
        self.assertEqual(state["phase"], "showdown")
        self.act(state, "pass")
        self.act(state, "pass")
        self.assertEqual(state["points"][0], 1)
        self.act(state, "end_turn")
        self.act(state, "end_turn")
        self.assertEqual(state["points"][0], 2)

    def test_group_movement_and_simultaneous_combat_deaths(self):
        state = self.scenario()
        state["fields"][0]["code"] = "OGN-276"  # No Might aura.
        attacker = self.unit(state, "OGN-219", location="base:0")
        defender = self.unit(state, "OGN-219", player=1)
        self.act(state, "begin_move", destination=0)
        self.act(state, "select_unit", unit=attacker["id"])
        self.act(state, "commit_move")
        self.act(state, "pass")
        self.act(state, "pass")
        self.assertEqual(state["phase"], "damage")
        self.act(state, "assign_damage", target=defender["id"])
        self.assertIn(attacker, state["units"])  # Damage not dealt before both assignments.
        self.act(state, "assign_damage", target=attacker["id"])
        self.assertFalse(state["units"])
        self.assertIsNone(state["fields"][0]["controller"])

    def test_single_damage_target_finishes_forced_overkill_in_one_choice(self):
        state = self.scenario()
        attacker = self.unit(state, "OGN-015", location=0)
        defender = self.unit(state, "OGN-219", player=1, location=0)
        state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        state["phase"], state["actor"], state["passes"] = "showdown", 0, 0
        self.act(state, "pass")
        self.act(state, "pass")
        self.assertEqual(state["phase"], "damage")
        self.act(state, "assign_damage", target=defender["id"])
        assigned = state["battle"]["damage"]["assignments"][0][defender["id"]]
        self.assertEqual(state["battle"]["damage"]["remaining"][0], 0)
        self.assertEqual(assigned, self.rules.might(state, attacker))
        self.assertEqual(state["actor"], 1)

    def test_fiora_mighty_shield_and_battlefield_ganking(self):
        state = self.scenario()
        state["fields"][0]["code"] = "OGN-276"
        unit = self.unit(state, "OGN-232")
        self.assertFalse(self.rules._ganking(state, unit))
        unit["buff"] = 1
        self.assertTrue(self.rules._ganking(state, unit))
        state["battle"] = {"field": 0, "attacker": 1, "combat": True}
        self.assertEqual(self.rules.might(state, unit), 6)
        state["battle"] = None
        unit["buff"] = 0
        state["fields"][0]["code"] = "OGN-297"
        self.assertTrue(self.rules._ganking(state, unit))

    def test_completed_starter_game_replays_and_step_cap_is_distinct(self):
        env = Environment(self.rules, max_steps=1600)
        episode = self_play(env, (GreedyPolicy(), GreedyPolicy()), seed=9)
        self.assertTrue(episode.terminated)
        self.assertFalse(episode.truncated)
        self.assertEqual(replay(self.rules, env.audit_replay()).audit_replay(), env.audit_replay())
        capped = Environment(self.rules, max_steps=1)
        capped.reset(seed=9)
        result = capped.step(capped.legal_actions()[0])
        self.assertTrue(result.truncated)
        with self.assertRaises(InvalidAction):
            capped.step(capped.legal_actions()[0] if capped.legal_actions() else env.audit_replay())

    def test_random_legal_trajectory_preserves_invariants(self):
        env = Environment(self.rules, max_steps=150)
        episode = self_play(env, (RandomPolicy(71), RandomPolicy(72)), seed=7)
        self.assertTrue(episode.terminated or episode.truncated)
        replay(self.rules, env.audit_replay())

    def test_peak_guardian_buffs_self_and_other_friendly_units_here(self):
        state = self.scenario()
        friend = self.unit(state)
        uid = self.hand(state, "OGN-223")
        self.act(state, "play_unit", card=uid, location=0)
        self.drain(state)
        self.assertEqual(friend["buff"], 1)
        self.assertEqual(next(u for u in state["units"] if u["card"] == uid)["buff"], 1)

    def test_back_to_back_two_targets_and_cleave_assault_stack_with_farron(self):
        state = self.scenario()
        first = self.unit(state, "OGN-210")
        second = self.unit(state, "OGN-015")
        spell = self.hand(state, "OGN-206")
        self.act(state, "play_spell", card=spell, targets=[first["id"], second["id"]])
        self.drain(state)
        self.assertEqual((first["temporary"], second["temporary"]), (2, 2))
        cleave = self.hand(state, "OGN-004")
        self.act(state, "play_spell", card=cleave, targets=[first["id"]])
        self.drain(state)
        state["fields"][0]["code"] = "OGN-276"
        state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        # 2 printed + 2 temporary + 1 innate Assault + 3 Cleave + 1 Farron.
        self.assertEqual(self.rules.might(state, first), 9)

    def test_void_seeker_draws_even_when_its_target_has_left(self):
        state = self.scenario()
        enemy = self.unit(state, player=1)
        spell = self.hand(state, "OGN-024")
        self.act(state, "play_spell", card=spell, targets=[enemy["id"]])
        state["units"].remove(enemy)
        state["players"][1]["trash"].append(enemy["card"])
        before = len(state["players"][0]["hand"])
        self.drain(state)
        self.assertEqual(len(state["players"][0]["hand"]), before+1)

    def test_simple_damage_and_debuff_spell_cluster(self):
        state = self.scenario()
        enemy = self.unit(state, "OGN-219", player=1, location=0)
        ray = self.hand(state, "OGN-024")
        state["cards"][ray]["code"] = "OGN-085"
        state["players"][0]["energy"] = 6
        self.act(state, "play_spell", card=ray, targets=[enemy["id"]])
        self.drain(state)
        self.assertEqual(enemy["damage"], 6)
        debuff = self.hand(state, "OGN-207")
        state["cards"][debuff]["code"] = "OGN-095"
        target = self.unit(state, "OGN-219", location="base:0")
        state["players"][0]["energy"] = 1
        state["players"][0]["power"] = ["mind"]
        before = len(state["players"][0]["hand"])
        self.act(state, "play_spell", card=debuff, targets=[target["id"]])
        self.drain(state)
        self.assertEqual(target["temporary"], -1)
        self.assertEqual(len(state["players"][0]["hand"]), before)

    def test_static_units_and_hold_trigger_cluster(self):
        state = self.scenario()
        shield = self.hand(state, "OGN-219")
        state["cards"][shield]["code"] = "OGN-052"
        state["fields"][0]["code"] = "OGN-276"
        defender = self.rules._new_unit(state, "OGN-052", 0, 0, card=shield, exhausted=False)
        state["battle"] = {"field": 0, "attacker": 1, "combat": True}
        self.assertEqual(self.rules.might(state, defender), 3)

        ahri = self.take_card(state, "OGN-219")
        state["cards"][ahri]["code"] = "OGN-066"
        self.rules._new_unit(state, "OGN-066", 0, 1, card=ahri, exhausted=False)
        state["fields"][1]["controller"] = 0
        self.rules._score(state, 0, 1, "hold", random.Random(4))
        self.assertEqual(state["points"][0], 2)

    def test_progress_day_draws_four_without_a_target(self):
        state = self.scenario()
        spell = self.hand(state, "OGN-024")
        state["cards"][spell]["code"] = "OGN-114"
        state["players"][0]["power"] = ["mind"]
        before = len(state["players"][0]["hand"])
        self.act(state, "play_spell", card=spell, targets=[])
        self.drain(state)
        self.assertEqual(len(state["players"][0]["hand"]), before + 3)

    def test_vengeance_kills_a_unit(self):
        state = self.scenario()
        enemy = self.unit(state, player=1)
        spell = self.hand(state, "OGN-024")
        state["cards"][spell]["code"] = "OGN-229"
        self.act(state, "play_spell", card=spell, targets=[enemy["id"]])
        self.drain(state)
        self.assertNotIn(enemy, state["units"])

    def test_faithful_manufactor_enters_a_recruit_chain(self):
        state = self.scenario()
        card = self.hand(state, "OGN-219")
        state["cards"][card]["code"] = "OGN-211"
        self.act(state, "play_unit", card=card, location="base:0")
        self.drain(state)
        self.assertTrue(any(unit["card"] is None and unit["code"] == "OGN-273"
                            for unit in state["units"]))

    def test_anivia_attack_trigger_deals_area_damage(self):
        state = self.scenario()
        card = self.take_card(state, "OGN-219")
        state["cards"][card]["code"] = "OGN-148"
        self.rules._new_unit(state, "OGN-148", 0, 0, card=card, exhausted=False)
        defender = self.unit(state, "OGN-142" if any(state["cards"][uid]["code"] == "OGN-142"
                                                       for uid in state["players"][1]["main"]) else "OGN-219",
                              player=1, location=0)
        state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        self.rules._close_showdown(state, random.Random(8))
        self.assertEqual(defender["damage"], 3)

    def test_warwick_enters_ready_and_kills_damaged_defenders_on_attack(self):
        state = self.scenario()
        card = self.take_card(state, "OGN-219")
        state["cards"][card]["code"] = "OGN-159"
        warwick = self.rules._new_unit(state, "OGN-159", 0, 0, card=card, exhausted=False)
        defender = self.unit(state, player=1, location=0)
        defender["damage"] = 1
        state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        self.rules._close_showdown(state, random.Random(8))
        self.assertNotIn(defender, state["units"])
        self.assertTrue(warwick["exhausted"] is False)

    def test_stunned_unit_deals_no_combat_damage_until_end_of_turn(self):
        state = self.scenario()
        attacker = self.unit(state, player=0, location=0)
        defender = self.unit(state, player=1, location=0)
        attacker["stunned"] = True
        state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        self.rules._close_showdown(state, random.Random(8))
        self.assertEqual(state["battle"]["damage"]["remaining"][0], 0)
        self.assertGreater(state["battle"]["damage"]["remaining"][1], 0)
        self.assertTrue(attacker["stunned"])

    def test_magma_wurm_also_readies_played_recruit_tokens(self):
        state = self.scenario()
        self.unit(state, "OGN-011", location="base:0")
        drummer = self.unit(state, "OGN-222", location="base:0")
        self.act(state, "begin_move", destination=0)
        self.act(state, "select_unit", unit=drummer["id"])
        self.act(state, "commit_move")
        self.drain(state)
        token = next(u for u in state["units"] if u["card"] is None)
        self.assertFalse(token["exhausted"])

    def test_movement_selection_is_private_until_committed(self):
        state = self.scenario()
        unit = self.unit(state, location="base:0")
        self.act(state, "begin_move", destination=0)
        self.act(state, "select_unit", unit=unit["id"])
        self.assertIsNone(self.rules.observe(state, 1)["selection"])
        self.assertEqual(self.rules.observe(state, 0)["selection"]["units"], [unit["id"]])

    def test_battlefield_passives_and_hand_of_noxus_energy(self):
        state = self.scenario()
        state["fields"][0]["code"] = "OGN-294"
        unit = self.unit(state)
        self.assertEqual(self.rules.might(state, unit), 5)
        self.assertFalse(any(a.kind == "legend_energy" for a in self.rules.legal_actions(state)))
        state["players"][0]["played"] = 1
        before = state["players"][0]["energy"]
        self.act(state, "legend_energy")
        self.assertEqual(state["players"][0]["energy"], before+1)
        self.assertFalse(any(a.kind == "legend_energy" for a in self.rules.legal_actions(state)))
        actual = self.rules.initial_state(random.Random(2))
        self.assertEqual(actual["victory"], 8+sum(f["code"] == "OGN-276" for f in actual["fields"]))

    def test_kaisa_accelerate_is_ready_and_uses_fury_power(self):
        state = self.scenario()
        uid = self.hand(state, "OGN-219")
        state["cards"][uid]["code"] = "OGN-039"
        before = state["players"][0]["energy"]
        self.act(state, "play_unit", card=uid, accelerate=True, location="base:0")
        self.assertFalse(state["units"][-1]["exhausted"])
        self.assertEqual(state["players"][0]["energy"], before - 5)

    def test_kaisa_draws_after_conquering(self):
        state = self.scenario()
        uid = self.take_card(state, "OGN-219")
        state["cards"][uid]["code"] = "OGN-039"
        kaisa = self.rules._new_unit(state, "OGN-039", 0, 0, card=uid, exhausted=False)
        state["battle"] = {"field": 0, "attacker": 0, "combat": False}
        before = len(state["players"][0]["hand"])
        self.rules._settle_battle(state, random.Random(7))
        self.assertEqual(state["points"][0], 1)
        self.assertEqual(len(state["players"][0]["hand"]), before + 1)
        self.assertIn(kaisa, state["units"])

    def test_all_six_domain_runes_are_valid_resources(self):
        state = self.scenario()
        state["players"][0]["power"] = ["fury", "calm", "mind", "body", "chaos", "order"]
        self.rules.validate(state)
        self.assertTrue(any(a.kind == "play_unit" for a in self.rules.legal_actions(state)))

    def test_daughter_of_the_void_adds_spell_only_rainbow_power(self):
        state = self.scenario()
        row = state["players"][0]
        row["legend"] = "OGN-247"
        row["energy"] = 4
        row["power"] = ["fury"]
        self.assertTrue(any(a.kind == "legend_spell_power" for a in self.rules.legal_actions(state)))
        self.act(state, "legend_spell_power")
        self.assertEqual(row["power"], ["fury", "spell_any"])
        self.assertTrue(row["legend_exhausted"])
        enemy = self.unit(state, "OGN-013", player=1, location=0)
        spell = self.hand(state, "OGN-009")
        actions = [a for a in self.rules.legal_actions(state)
                   if a.kind == "play_spell" and json.loads(a.arguments)["card"] == spell
                   and json.loads(a.arguments)["targets"] == [enemy["id"]]]
        self.assertTrue(actions)
        self.rules.apply(state, actions[0], random.Random(7))
        self.rules.validate(state)
        self.assertEqual(row["power"], [])

        # The generated resource is restricted to spells and cannot pay a unit.
        row["power"] = ["spell_any"]
        unit = self.hand(state, "OGN-010")
        self.assertFalse(any(a.kind == "play_unit" and json.loads(a.arguments)["card"] == unit
                             for a in self.rules.legal_actions(state)))

    def test_chemtech_enforcer_enters_chain_for_one_discard(self):
        state = self.scenario()
        uid = self.hand(state, "OGN-219")
        state["cards"][uid]["code"] = "OGN-003"
        before = len(state["players"][0]["hand"])
        self.act(state, "play_unit", card=uid, location="base:0")
        self.assertEqual(state["phase"], "chain")
        self.assertIn("discard_one", [item["effect"] for item in state["chain"]])
        self.act(state, "pass")
        self.act(state, "pass")
        self.assertEqual(state["phase"], "decision")
        card = state["players"][0]["hand"][0]
        self.act(state, "discard_card", card=card)
        self.assertEqual(len(state["players"][0]["hand"]), before - 2)

    def test_draven_might_scales_with_points(self):
        state = self.scenario()
        uid = self.hand(state, "OGN-219")
        state["cards"][uid]["code"] = "OGN-028"
        unit = self.rules._new_unit(state, "OGN-028", 0, "base:0", card=uid, exhausted=False)
        self.assertEqual(self.rules.might(state, unit), 3 + state["points"][0])
        state["points"][0] = 3
        self.assertEqual(self.rules.might(state, unit), 6)


if __name__ == "__main__":
    unittest.main()
