import copy
import random
import unittest

from riftbound.card_registry import spiritforged_registry
from riftbound.expansion_catalog import load_expansions
from riftbound.spiritforged import SpiritforgedRules
from riftbound.engine import Action, RulesUnavailable
from riftbound.support import DEFAULT_FIELDS


ORIGINS = __import__("json").load(open("riftbound/data/origins.json", encoding="utf-8"))
ORIGIN_BY_CODE = {row["code"]: row for row in ORIGINS}
EXPANSION_BY_ID = {row["id"]: row for row in load_expansions(set_code="SFD")}


def legal_deck(target, legend, champion):
    """Build a deterministic legal deck containing one SFD test card."""
    domains = set(ORIGIN_BY_CODE[legend]["domains"])
    main = [champion] * 3 + [target] * 3
    for row in ORIGINS:
        if len(main) >= 40 or row["code"] in {champion, target}:
            continue
        if row["type"] not in {"unit", "gear", "spell"} or row["token"] or row["signature"]:
            continue
        if not set(row["domains"]) <= domains:
            continue
        main.extend([row["code"]] * min(3, 40 - len(main)))
    rune_by_domain = {"fury": "OGN-007", "calm": "OGN-042", "mind": "OGN-089",
                      "body": "OGN-126", "chaos": "OGN-166", "order": "OGN-214"}
    rune_domains = sorted(domains)
    first, second = rune_domains[0], rune_domains[-1]
    return {"legend": legend, "chosen_champion": champion, "main": main,
            "runes": [rune_by_domain[first]] * 6 + [rune_by_domain[second]] * 6,
            "battlefields": list(DEFAULT_FIELDS)}


def move_code_to_hand(state, player, code):
    row = state["players"][player]
    for zone in ("hand", "main"):
        for uid in list(row[zone]):
            if state["cards"][uid]["code"] == code:
                if zone == "main":
                    row[zone].remove(uid)
                    row["hand"].append(uid)
                return uid
    raise AssertionError(f"missing {code}")


class SpiritforgedExecutableTests(unittest.TestCase):
    def test_registry_is_namespaced_and_explicit(self):
        registry = spiritforged_registry()
        self.assertEqual(len(registry.executable_codes()), 188)
        self.assertEqual(registry.get("SFD-006-221").entry_effect, "enter_ready")
        self.assertEqual(registry.get("SFD-087-221").spell_effect, "draw_three")
        self.assertEqual(registry.get("SFD-106-221").spell_effect, "draw_mighty")
        self.assertEqual(registry.get("SFD-147-221").spell_effect, "return_all_units_gear")
        self.assertEqual(registry.get("SFD-001-221").target_scope, "friendly_field_unit")
        self.assertEqual(registry.get("SFD-005-221").spell_effect, "kill_gear_draw_two")
        self.assertEqual(registry.get("SFD-097-221").target_scope, "any_unit")
        self.assertEqual(registry.get("SFD-135-221").target_scope, "any_gear")
        self.assertEqual(registry.get("SFD-155-221").deathknell_effect, "play_gold_gear")
        self.assertEqual(registry.get("SFD-047-221").buff_effect, "ready_self")
        self.assertEqual(registry.get("SFD-072-221").entry_effect, "enter_ready_if_two_gear")
        self.assertEqual(registry.get("SFD-130-221").move_effect, "play_gold_gear")
        self.assertEqual(registry.get("SFD-137-221").move_effect, "buff_self_two_from_field")
        self.assertEqual(registry.get("SFD-159-221").might_effect, "plus_one_if_another_friendly_here")
        self.assertEqual(registry.get("SFD-167-221").deathknell_effect, "draw_two_if_mighty")
        self.assertEqual(registry.get("SFD-027-221").hold_effect, "draw_two")
        self.assertEqual(registry.get("SFD-061-221").entry_trigger, "return_gear_from_trash")
        self.assertEqual(registry.get("SFD-062-221").entry_trigger, "ready_another_friendly_mech")
        self.assertEqual(registry.get("SFD-152-221").hold_effect, "play_two_gold_gear")
        self.assertEqual(registry.get("SFD-171-221").global_effect, "tokens_enter_ready")
        self.assertEqual(registry.get("SFD-174-221").entry_trigger, "play_four_gold_gear")
        self.assertEqual(registry.get("SFD-098-221").additional_cost_effect, "buff_self")
        self.assertEqual(registry.get("SFD-032-221").entry_trigger, "optional_kill_gear")
        self.assertEqual(registry.get("SFD-035-221").hold_effect, "optional_return_card_from_trash")
        self.assertEqual(registry.get("SFD-038-221").move_effect, "buff_another_on_move")
        self.assertEqual(registry.get("SFD-039-221").entry_trigger, "legend_toggle")
        self.assertEqual(registry.get("SFD-071-221").entry_effect, "enter_ready_if_another_mech")
        self.assertEqual(registry.get("SFD-071-221").global_effect, "mechs_deflect_ganking")
        self.assertEqual(registry.get("SFD-065-221").global_effect, "mechs_vision")
        self.assertEqual(registry.get("SFD-031-221").spell_effect, "play_sand_soldier")
        self.assertEqual(registry.get("SFD-034-221").spell_effect, "buff_two")
        self.assertEqual(registry.get("SFD-066-221").spell_effect, "debuff_two")
        self.assertEqual(registry.get("SFD-076-221").cost_reduction_effect, "control_mech")
        self.assertEqual(registry.get("SFD-007-221").entry_trigger, "ganking_target")
        self.assertEqual(registry.get("SFD-021-221").deathknell_effect, "play_two_mech")
        self.assertEqual(registry.get("SFD-089-221").global_effect, "mechs_plus_one")
        self.assertEqual(registry.get("SFD-012-221").cost_reduction_effect, "cards_played_floor_one")
        self.assertEqual(registry.get("SFD-015-221").placement_rule, "conquered_field_this_turn")
        self.assertEqual(registry.get("SFD-093-221").placement_rule, "occupied_enemy_field")
        self.assertEqual(registry.get("SFD-158-221").entry_trigger, "kill_small_enemy")
        self.assertEqual(registry.get("SFD-014-221").global_effect, "no_base_moves")
        self.assertEqual(registry.get("SFD-060-221").global_effect, "opponents_cant_score")
        self.assertIn("accelerate", registry.get("SFD-131-221").static_keywords)
        self.assertIn("assault_1", registry.get("SFD-028-221").static_keywords)
        self.assertEqual(registry.get("SFD-046-221").activated_effect, "gear_draw")
        self.assertEqual(registry.get("SFD-052-221").activated_effect, "gear_buff_three")
        self.assertEqual(registry.get("SFD-110-221").might_effect, "double_one_on_one")
        self.assertEqual(registry.get("SFD-116-221").conquer_effect, "damage_enemy_base_by_might")
        self.assertEqual(registry.get("SFD-166-221").spell_effect, "rally_the_troops")
        self.assertEqual(registry.get("SFD-163-221").spell_effect, "deathgrip")
        self.assertEqual(registry.get("SFD-163-221").target_scope, "friendly_unit")
        self.assertEqual(registry.get("SFD-168-221").activated_effect, "play_three_recruit")
        self.assertEqual(registry.get("SFD-028A-221").static_keywords, frozenset({"assault_1"}))
        self.assertEqual(registry.get("SFD-089A-221").global_effect, "mechs_plus_one")
        self.assertEqual(registry.get("SFD-149A-221").entry_trigger, "discard_one_draw_two")
        self.assertEqual(registry.get("SFD-003-221").spell_effect, "assault_two")
        self.assertEqual(registry.get("SFD-017-221").spell_effect, "sudden_storm")
        self.assertEqual(registry.get("SFD-040-221").target_scope, "attacking_unit")
        self.assertEqual(registry.get("SFD-070-221").spell_effect, "wages_of_pain")
        self.assertEqual(registry.get("SFD-100-221").global_effect, "draw_on_power_two")
        self.assertEqual(registry.get("SFD-123-221").combat_effect, "draw_one_on_win")
        self.assertEqual(registry.get("SFD-151-221").spell_effect, "buff_two_each")
        self.assertEqual(registry.get("SFD-181-221").global_effect, "mechs_shield")
        self.assertEqual(registry.get("SFD-041-221").move_effect, "apprentice_smith")
        self.assertEqual(registry.get("SFD-104-221").global_effect, "friendly_deflect")
        self.assertEqual(registry.get("SFD-171A-221").global_effect, "tokens_enter_ready")
        self.assertEqual(registry.get("SFD-227-221").combat_effect, "ahri_debuff")
        self.assertEqual(registry.get("SFD-227-STAR-221").combat_effect, "ahri_debuff")
        self.assertEqual(registry.get("SFD-235-221").move_effect, "score_on_third_move")
        self.assertEqual(registry.get("SFD-235-STAR-221").move_effect, "score_on_third_move")
        self.assertEqual(registry.get("SFD-236-221").entry_effect, "enter_ready_if_legion")
        self.assertEqual(registry.get("SFD-236-STAR-221").global_effect, "plus_one_friendly_here")
        self.assertEqual(registry.get("SFD-237-221").global_effect, "vision_recycle")
        self.assertEqual(registry.get("SFD-237-STAR-221").global_effect, "vision_recycle")
        self.assertEqual(registry.get("SFD-240-221").global_effect, "mechs_shield")
        self.assertEqual(registry.get("SFD-242-221").combat_effect, "draw_one_on_win")
        self.assertEqual(registry.get("SFD-055-221").cost_reduction_effect, "hold_points")
        self.assertIn("shield_5", registry.get("SFD-055-221").static_keywords)
        self.assertEqual(registry.get("SFD-223-221").entry_effect, "enter_ready_if_opponent_field")
        self.assertEqual(registry.get("SFD-223-STAR-221").conquer_effect, "return_self")
        self.assertEqual(registry.get("SFD-230-221").global_effect, "teemo_defend")
        self.assertEqual(registry.get("SFD-230-STAR-221").global_effect, "teemo_defend")
        self.assertEqual(registry.get("SFD-232-221").activated_effect, "spend_buff_four")
        self.assertEqual(registry.get("SFD-232-STAR-221").conquer_effect, "buff_self")
        self.assertEqual(registry.get("SFD-185-221").combat_effect, "draw_one_on_win")
        self.assertIn("untargetable_enemy", registry.get("SFD-105-221").static_keywords)
        self.assertEqual(registry.get("SFD-204-221").spell_effect, "ready_friendly_units")
        self.assertEqual(registry.get("SFD-110A-221").might_effect, "double_one_on_one")
        self.assertEqual(registry.get("SFD-233-221").conquer_effect, "damage_enemy_base_by_might")
        self.assertEqual(registry.get("SFD-233-STAR-221").conquer_effect, "damage_enemy_base_by_might")
        self.assertEqual(registry.get("SFD-044-221").additional_cost_effect, "return_gear")
        self.assertEqual(registry.get("SFD-132-221").entry_trigger, "return_friendly_enemy")
        self.assertEqual(registry.get("SFD-004-221").spell_effect, "ready_friendly_and_gold")
        self.assertIn("hidden", registry.get("SFD-004-221").static_keywords)
        self.assertEqual(registry.get("SFD-122-221").spell_effect, "draw_one_recycle_one")
        self.assertEqual(registry.get("SFD-138-221").entry_trigger, "optional_return_small_field_unit")
        self.assertIn("hidden", registry.get("SFD-138-221").static_keywords)
        self.assertEqual(registry.get("SFD-126-221").combat_effect, "loyal_pup_defend")
        self.assertEqual(registry.get("SFD-128-221").combat_effect, "overzealous_fan_defend")
        self.assertEqual(registry.get("SFD-189-221").activated_effect, "legend_rainbow")
        self.assertEqual(registry.get("SFD-244-221").activated_effect, "legend_rainbow")
        self.assertEqual(registry.get("SFD-192-221").entry_trigger, "ready_friendly_units")
        self.assertEqual(registry.get("SFD-020-221").combat_effect, "play_gold_gear")
        self.assertEqual(registry.get("SFD-020A-221").global_effect, "draven_combat_might")
        self.assertEqual(registry.get("SFD-196-221").spell_effect, "buff_debuff_pair")
        self.assertEqual(registry.get("SFD-196-221").target_scope, "any_unit")
        self.assertEqual(registry.get("SFD-196-221").target_max, 2)
        self.assertEqual(registry.get("SFD-194-221").spell_effect, "prevent_next_damage_draw")
        self.assertEqual(registry.get("SFD-194-221").target_scope, "any_unit")
        self.assertEqual(registry.get("SFD-013-221").additional_cost_effect, "blast_corps")
        self.assertEqual(registry.get("SFD-067-221").additional_cost_effect, "frostcoat_debuff")
        self.assertEqual(registry.get("SFD-067-221").additional_cost_power, 1)
        self.assertEqual(registry.get("SFD-083-221").activated_effect, "gear_energy_from_rainbow")
        self.assertEqual(registry.get("SFD-117-221").activated_effect, "gear_rainbow_from_energy")
        self.assertEqual(registry.get("SFD-045-221").counter_scope, "friendly_target")
        self.assertEqual(registry.get("SFD-025-221").placement_rule, "attacking_battlefield")
        self.assertEqual(registry.get("SFD-025-221").static_keywords, frozenset({"assault_2"}))
        self.assertEqual(registry.get("SFD-025A-221").placement_rule, "attacking_battlefield")
        self.assertEqual(registry.get("SFD-113-221").conquer_effect, "ready_self_once")
        self.assertEqual(registry.get("SFD-113A-221").conquer_effect, "ready_self_once")
        self.assertEqual(registry.get("SFD-069-221").conquer_effect, "play_gold_gear")
        self.assertEqual(registry.get("SFD-074-221").entry_trigger, "optional_kill_cheap_gear")
        self.assertEqual(registry.get("SFD-075-221").global_effect, "prize_progress")
        self.assertEqual(registry.get("SFD-091-221").entry_trigger, "optional_draw_or_buff")
        self.assertEqual(registry.get("SFD-149-221").entry_trigger, "discard_one_draw_two")
        self.assertEqual(registry.get("SFD-157-221").entry_trigger, "play_sand_soldier")
        self.assertEqual(registry.get("SFD-154-221").spell_effect, "play_sand_soldier_optional_order")
        self.assertIn("hidden", registry.get("SFD-154-221").static_keywords)
        self.assertEqual(registry.get("SFD-198-221").spell_effect, "arise_sand_soldiers")
        self.assertEqual(registry.get("SFD-063-221").global_effect, "chemtech_cask")
        self.assertEqual(registry.get("SFD-160-221").additional_cost_effect, "kill_gear")
        self.assertEqual(registry.get("SFD-142-221").global_effect, "draw_when_chosen_spell")
        self.assertEqual(registry.get("SFD-144-221").global_effect, "draw_on_friendly_spell_target")
        self.assertEqual(registry.get("SFD-169-221").global_effect, "altar_of_memories")
        self.assertEqual(registry.get("SFD-081-221").entry_trigger, "card_sharp")
        self.assertEqual(registry.get("SFD-162-221").spell_effect, "kill_small_unit_and_gold")
        self.assertEqual(registry.get("SFD-162-221").target_scope, "field_unit_might_le_2")
        self.assertEqual(registry.get("SFD-175-221").entry_trigger, "buff_other_units_two")
        self.assertEqual(registry.get("SFD-179-221").move_effect, "play_recruit_three")
        self.assertEqual(registry.get("SFD-209-221").global_effect, "forgotten_monument")
        self.assertEqual(registry.get("SFD-210-221").global_effect, "hall_of_legends")
        self.assertEqual(registry.get("SFD-212-221").global_effect, "minefield")
        self.assertEqual(registry.get("SFD-216-221").global_effect, "rockfall_path")
        self.assertEqual(registry.get("SFD-217-221").global_effect, "seat_of_power")
        self.assertEqual(registry.get("SFD-218-221").global_effect, "sunken_temple")
        self.assertEqual(registry.get("SFD-219-221").global_effect, "papertree")
        self.assertEqual(registry.get("SFD-220-221").global_effect, "treasure_hoard")
        self.assertEqual(registry.get("SFD-207-221").global_effect, "emperor_dais")
        self.assertEqual(registry.get("SFD-213-221").global_effect, "ornns_forge")
        self.assertEqual(registry.get("SFD-214-221").global_effect, "power_nexus")
        self.assertEqual(registry.get("SFD-201-221").global_effect, "chem_baroness")
        self.assertEqual(registry.get("SFD-215-221").global_effect, "ravenbloom_conservatory")
        self.assertEqual(registry.get("SFD-197-221").activated_effect, "emperor_sands_soldier")
        self.assertEqual(registry.get("SFD-247-221").activated_effect, "emperor_sands_soldier")
        self.assertEqual(registry.get("SFD-203-221").global_effect, "battle_mistress")
        self.assertEqual(registry.get("SFD-250-221").global_effect, "battle_mistress")
        self.assertEqual(registry.get("SFD-205-221").global_effect, "grand_duelist")
        self.assertEqual(registry.get("SFD-251-221").global_effect, "grand_duelist")
        self.assertEqual(registry.get("SFD-249-221").global_effect, "chem_baroness")
        self.assertEqual(registry.get("SFD-010-221").cost_reduction_effect, "void_drone_from_anywhere")
        self.assertEqual(registry.get("SFD-121-221").global_effect, "gold_on_hidden_play")
        self.assertEqual(registry.get("SFD-164-221").spell_effect, "kill_field_unit")
        self.assertEqual(registry.get("SFD-057-221").global_effect, "irelia_fervent")
        self.assertEqual(registry.get("SFD-057A-221").global_effect, "irelia_fervent")
        self.assertEqual(registry.get("SFD-225-STAR-221").global_effect, "irelia_fervent")
        self.assertEqual(registry.get("SFD-058-221").entry_trigger, "ornn_search")
        self.assertEqual(registry.get("SFD-058-221").hold_effect, "ornn_search")
        self.assertEqual(registry.get("SFD-058A-221").entry_trigger, "ornn_search")
        self.assertEqual(registry.get("SFD-082-221").combat_effect, "ezreal_attack")
        self.assertEqual(registry.get("SFD-029-221").global_effect, "friendly_units_accelerate")
        self.assertEqual(registry.get("SFD-103-221").cost_reduction_effect, "mighty_units")
        self.assertEqual(registry.get("SFD-120-221").conquer_effect, "sivir_excess_damage")
        self.assertEqual(registry.get("SFD-143-221").global_effect, "sivir_mercenary")
        self.assertEqual(registry.get("SFD-177-221").global_effect, "azir_sovereign")
        self.assertEqual(registry.get("SFD-180-221").global_effect, "fiora_worthy")
        self.assertEqual(registry.get("SFD-195-221").global_effect, "blade_dancer")
        self.assertEqual(registry.get("SFD-199-221").activated_effect, "prodigal_draw")
        self.assertEqual(registry.get("SFD-125-221").move_effect, "fae_porter")
        self.assertEqual(registry.get("SFD-165-221").deathknell_effect, "play_cheap_trash_unit")
        self.assertEqual(registry.behavior_id("SFD-222-221"), "OGN-040")
        self.assertIsNone(registry.get("SFD-002-221"))

    def test_unregistered_sfd_card_is_rejected(self):
        deck = legal_deck("SFD-002-221", "OGN-247", "OGN-039")
        with self.assertRaises(RulesUnavailable):
            SpiritforgedRules([deck, deck])

    def test_beast_below_uses_a_friendly_enemy_pair_window(self):
        deck = legal_deck("SFD-132-221", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(6))
        card = move_code_to_hand(state, 0, "SFD-132-221")
        friendly = rules._new_unit(state, "OGN-001", 0, "base:0", exhausted=False)
        enemy = rules._new_unit(state, "OGN-001", 1, "base:1", exhausted=False)
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 20
        state["players"][0]["power"] = ["chaos"] * 20
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == card
                    and __import__("json").loads(action.arguments)["location"] == "base:0")
        rules.apply(state, play, random.Random(7))
        self.assertEqual(state["decision"]["target_pairs"], [[friendly["id"], enemy["id"]]])
        rules.apply(state, Action.make("choose_target", target=friendly["id"]), random.Random(8))
        rules.apply(state, Action.make("choose_target", target=enemy["id"]), random.Random(9))
        rules.apply(state, Action.make("confirm_targets"), random.Random(10))
        rules.apply(state, Action.make("pass"), random.Random(11))
        rules.apply(state, Action.make("pass"), random.Random(12))
        self.assertNotIn(friendly, state["units"])
        self.assertNotIn(enemy, state["units"])

    def test_bushwhack_uses_common_spell_resolution_and_ready_play_window(self):
        deck = legal_deck("SFD-004-221", "OGN-251", "OGN-202")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(13))
        card = move_code_to_hand(state, 0, "SFD-004-221")
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["chaos"] * 10
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_spell"
                    and __import__("json").loads(action.arguments)["card"] == card)
        rules.apply(state, play, random.Random(14))
        rules.apply(state, Action.make("pass"), random.Random(15))
        rules.apply(state, Action.make("pass"), random.Random(16))
        self.assertTrue(state["players"][0]["ready_play"])
        self.assertTrue(any(gear["code"] == "SFD-T03" for gear in state["players"][0]["gear"]))

    def test_called_shot_opens_a_two_card_reveal_window(self):
        deck = legal_deck("SFD-122-221", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(17))
        card = move_code_to_hand(state, 0, "SFD-122-221")
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["chaos"] * 10
        top = list(state["players"][0]["main"][:2])
        self.assertEqual(len(top), 2)
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_spell"
                    and __import__("json").loads(action.arguments)["card"] == card)
        rules.apply(state, play, random.Random(18))
        rules.apply(state, Action.make("pass"), random.Random(19))
        rules.apply(state, Action.make("pass"), random.Random(20))
        self.assertEqual(state["phase"], "reveal")
        rules.apply(state, Action.make("choose_revealed", card=top[0]), random.Random(21))
        rules.apply(state, Action.make("confirm_revealed"), random.Random(22))
        self.assertIn(top[0], state["players"][0]["hand"])
        self.assertEqual(state["players"][0]["main"][-1], top[1])

    def test_ornn_entry_and_hold_share_top_four_gear_window(self):
        deck = legal_deck("SFD-058-221", "OGN-261", "OGN-079")
        # Force one legal Calm Gear into the deterministic deck so the
        # selection branch is covered without making the test depend on a
        # shuffled card order.
        deck["main"][-1] = "OGN-060"
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(181))
        card = move_code_to_hand(state, 0, "SFD-058-221")
        row = state["players"][0]
        gear = next(uid for uid in row["main"]
                    if rules.cards[state["cards"][uid]["code"]]["type"] == "gear")
        top = [gear] + [uid for uid in row["main"] if uid != gear][:3]
        row["main"] = top + [uid for uid in row["main"] if uid not in top]
        state["phase"], state["actor"] = "main", 0
        row["energy"], row["power"] = 10, ["calm"] * 10
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == card)
        rules.apply(state, play, random.Random(182))
        rules.apply(state, Action.make("pass"), random.Random(183))
        rules.apply(state, Action.make("pass"), random.Random(184))
        self.assertEqual(state["phase"], "reveal")
        self.assertIn(gear, state["reveal"]["choices"])
        rules.apply(state, Action.make("choose_revealed", card=gear), random.Random(185))
        rules.apply(state, Action.make("confirm_revealed"), random.Random(186))
        self.assertIn(gear, row["hand"])
        self.assertIsNone(state.get("reveal"))

        hold_state = rules.initial_state(random.Random(187))
        holder = rules._new_unit(hold_state, "SFD-058-221", 0, 0, exhausted=False)
        hold_state["fields"][0]["controller"] = 0
        rules._score(hold_state, 0, 0, "hold", random.Random(188))
        self.assertEqual(hold_state["optional"][0]["effect"], "ornn_search")
        rules.apply(hold_state, Action.make(
            "optional_effect", optional=hold_state["optional"][0]["id"], accept=True),
            random.Random(189))
        self.assertEqual(hold_state["phase"], "reveal")
        rules.apply(hold_state, Action.make("confirm_revealed"), random.Random(190))
        self.assertIsNone(hold_state.get("reveal"))
        self.assertFalse(hold_state.get("optional"))

    def test_batch_sivir_fiora_azir_ezreal_registry_modifiers(self):
        sivir_deck = legal_deck("SFD-120-221", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([sivir_deck, sivir_deck])
        state = rules.initial_state(random.Random(191))
        sivir = rules._new_unit(state, "SFD-120-221", 0, 0, exhausted=False)
        self.assertEqual(rules._deflect(state, sivir), 2)
        state["players"][0]["rainbow_spent_turn"] = 2
        mercenary = rules._new_unit(state, "SFD-143-221", 0, 0, exhausted=False)
        self.assertTrue(rules._ganking(state, mercenary))
        self.assertEqual(rules.might(state, mercenary),
                         rules.cards["SFD-143-221"]["might"] + 2)

        fiora_state = rules.initial_state(random.Random(192))
        fiora = rules._new_unit(fiora_state, "SFD-180-221", 0, "base:0", exhausted=False)
        target = rules._new_unit(fiora_state, "OGN-219", 0, "base:0", exhausted=True)
        target["temporary"] = 1
        fiora_state["players"][0]["power"] = ["order"]
        rules._cleanup(fiora_state, random.Random(193))
        fiora_effect = next(item for item in fiora_state["optional"]
                            if item["effect"] == "fiora_ready"
                            and item["target"] == target["id"])
        rules.apply(fiora_state, Action.make("optional_effect",
                                             optional=fiora_effect["id"], accept=True), random.Random(194))
        self.assertFalse(target["exhausted"])
        self.assertEqual(fiora_state["players"][0]["power"], [])

        azir = rules._new_unit(state, "SFD-177-221", 0, 0, exhausted=False)
        token = rules._new_unit(state, "SFD-T04", 0, "base:0", exhausted=False)
        state["phase"], state["actor"] = "main", 0
        rules._effect_azir_sovereign(state, {"source": azir["id"], "owner": 0, "field": 0}, random.Random(194))
        azir_effect = next(item for item in state["optional"]
                           if item["effect"] == "azir_move_tokens")
        state["chain_return"] = "main"
        rules.apply(state, Action.make("optional_effect",
                                       optional=azir_effect["id"], accept=True), random.Random(195))
        rules.apply(state, Action.make("choose_target", target=token["id"]), random.Random(196))
        rules.apply(state, Action.make("confirm_targets"), random.Random(197))
        self.assertEqual(token["location"], 0)
        self.assertTrue(token["exhausted"])

        ezreal_deck = legal_deck("SFD-082-221", "OGN-247", "OGN-039")
        ezreal_rules = SpiritforgedRules([ezreal_deck, ezreal_deck])
        ezreal_state = ezreal_rules.initial_state(random.Random(198))
        ezreal = ezreal_rules._new_unit(ezreal_state, "SFD-082-221", 0, 0, exhausted=False)
        ezreal_state["fields"][0]["controller"] = 0
        ezreal_state["phase"], ezreal_state["actor"] = "main", 0
        ezreal_state["players"][0]["power"] = ["mind"]
        action = next(action for action in ezreal_rules.legal_actions(ezreal_state)
                      if action.kind == "unit_registry_ability"
                      and __import__("json").loads(action.arguments)["unit"] == ezreal["id"])
        ezreal_rules.apply(ezreal_state, action, random.Random(199))
        self.assertEqual(ezreal["location"], "base:0")
        self.assertTrue(ezreal["exhausted"])

    def test_reksai_grants_accelerate_to_non_hand_free_unit(self):
        deck = legal_deck("SFD-029-221", "OGN-247", "OGN-039")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(200))
        source = rules._new_unit(state, "SFD-029-221", 0, "base:0", exhausted=False)
        card = next(uid for uid in state["players"][0]["main"]
                    if rules.cards[state["cards"][uid]["code"]]["type"] == "unit")
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["mind"] * 10
        rules._free_play_revealed_card(
            state, 0, card, {"effect": "test_free", "owner": 0}, random.Random(201),
            ignore_energy=True, card_owner=0)
        self.assertIsNotNone(state.get("decision"))
        self.assertTrue(state["decision"].get("accelerate"))
        self.assertEqual(state["decision"]["accelerate"]["unit"],
                         next(unit["id"] for unit in state["units"]
                              if unit["card"] == card))

    def test_blade_dancer_and_prodigal_legends_use_shared_choice_windows(self):
        deck = legal_deck("OGN-066", "OGN-261", "OGN-079")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(202))
        state["players"][0]["legend"] = "SFD-195-221"
        state["players"][0]["power"] = ["any"]
        target = rules._new_unit(state, "OGN-219", 0, "base:0", exhausted=True)
        triggers = rules._spell_choice_triggers(
            state, 0, {"card": "synthetic", "owner": 0}, [target["id"]])
        self.assertEqual(triggers, [])
        self.assertEqual(state["optional"][0]["effect"], "blade_dancer_ready_target")
        rules.apply(state, Action.make(
            "optional_effect", optional=state["optional"][0]["id"], accept=True), random.Random(203))
        self.assertFalse(target["exhausted"])
        self.assertTrue(state["players"][0]["legend_exhausted"])

        state["players"][0]["legend"] = "SFD-199-221"
        state["players"][0]["legend_exhausted"] = False
        state["players"][0]["enemy_choices_turn"] = 2
        state["phase"], state["actor"] = "chain", 0
        before = len(state["players"][0]["hand"])
        self.assertTrue(any(action.kind == "legend_prodigal_draw"
                            for action in rules.legal_actions(state)))
        rules.apply(state, Action.make("legend_prodigal_draw"), random.Random(204))
        self.assertEqual(len(state["players"][0]["hand"]), before + 1)

    def test_fae_porter_uses_optional_chaos_target_after_move(self):
        deck = legal_deck("SFD-125-221", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(205))
        source = rules._new_unit(state, "SFD-125-221", 0, "base:0", exhausted=False)
        target = rules._new_unit(state, "OGN-219", 0, "base:0", exhausted=False)
        state["fields"][0]["controller"] = 0
        state["players"][0]["power"] = ["chaos"]
        state["chain_return"] = "main"
        rules._resolve_move(state, [source], 0, 0, random.Random(206))
        self.assertEqual(state["optional"][0]["effect"], "fae_porter_move")
        rules.apply(state, Action.make(
            "optional_effect", optional=state["optional"][0]["id"], accept=True), random.Random(207))
        rules.apply(state, Action.make("choose_target", target=target["id"]), random.Random(208))
        self.assertEqual(target["location"], 0)
        self.assertEqual(state["players"][0]["power"], [])

    def test_windsinger_optional_return_has_a_target_window(self):
        deck = legal_deck("SFD-138-221", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(23))
        card = move_code_to_hand(state, 0, "SFD-138-221")
        target = rules._new_unit(state, "OGN-003", 1, 0, exhausted=False)
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["chaos"] * 10
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == card
                    and __import__("json").loads(action.arguments)["location"] == "base:0")
        rules.apply(state, play, random.Random(24))
        rules.apply(state, Action.make("pass"), random.Random(25))
        rules.apply(state, Action.make("pass"), random.Random(26))
        self.assertEqual(state["phase"], "optional")
        optional = state["optional"][0]["id"]
        rules.apply(state, Action.make("optional_effect", optional=optional, accept=True), random.Random(27))
        self.assertIn(target["id"], state["decision"]["targets"])
        rules.apply(state, Action.make("choose_target", target=target["id"]), random.Random(28))
        self.assertNotIn(target, state["units"])

    def test_loyal_pup_defend_opens_a_move_optional(self):
        deck = legal_deck("SFD-126-221", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(29))
        pup = rules._new_unit(state, "SFD-126-221", 1, "base:1", exhausted=False)
        rules._new_unit(state, "OGN-003", 1, 0, exhausted=False)
        rules._new_unit(state, "OGN-003", 0, 0, exhausted=False)
        state.update(phase="showdown", actor=0, focus=0, passes=0,
                     battle={"field": 0, "attacker": 0, "combat": True})
        rules._close_showdown(state, random.Random(30))
        rules.apply(state, Action.make("pass"), random.Random(31))
        rules.apply(state, Action.make("pass"), random.Random(32))
        self.assertEqual(state["phase"], "optional")
        optional = state["optional"][0]["id"]
        rules.apply(state, Action.make("optional_effect", optional=optional, accept=True), random.Random(33))
        self.assertEqual(pup["location"], 0)

    def test_overzealous_fan_defend_targets_an_attacker(self):
        deck = legal_deck("SFD-128-221", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(34))
        fan = rules._new_unit(state, "SFD-128-221", 1, 0, exhausted=False)
        attacker = rules._new_unit(state, "OGN-003", 0, 0, exhausted=False)
        state.update(phase="showdown", actor=0, focus=0, passes=0,
                     battle={"field": 0, "attacker": 0, "combat": True})
        rules._close_showdown(state, random.Random(35))
        rules.apply(state, Action.make("pass"), random.Random(36))
        rules.apply(state, Action.make("pass"), random.Random(37))
        self.assertEqual(state["phase"], "optional")
        optional = state["optional"][0]["id"]
        rules.apply(state, Action.make("optional_effect", optional=optional, accept=True), random.Random(38))
        self.assertEqual(state["decision"]["targets"], [attacker["id"]])
        rules.apply(state, Action.make("choose_target", target=attacker["id"]), random.Random(39))
        self.assertNotIn(fan, state["units"])
        self.assertEqual(attacker["location"], "base:0")

    def test_fire_below_the_mountain_exposes_reaction_resource_action(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(40))
        state["players"][0]["legend"] = "SFD-189-221"
        state.update(phase="showdown", actor=0, focus=0, passes=0)
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "legend_rainbow")
        rules.apply(state, action, random.Random(41))
        self.assertTrue(state["players"][0]["legend_exhausted"])
        self.assertEqual(state["players"][0]["power"][-1], "any")

    def test_shurelyas_requiem_uses_the_common_gear_entry_trigger(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(42))
        gear_card = "p0:test-shurelya"
        state["cards"][gear_card] = {"code": "SFD-192-221", "owner": 0}
        state["players"][0]["hand"].append(gear_card)
        unit = rules._new_unit(state, "OGN-003", 0, "base:0", exhausted=True)
        state.update(phase="main", actor=0)
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["calm", "mind"]
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_gear"
                    and __import__("json").loads(action.arguments)["card"] == gear_card)
        rules.apply(state, play, random.Random(43))
        rules.apply(state, Action.make("pass"), random.Random(44))
        rules.apply(state, Action.make("pass"), random.Random(45))
        self.assertFalse(unit["exhausted"])

    def test_draven_vanquisher_has_shared_combat_token_and_might_hooks(self):
        deck = legal_deck("SFD-020-221", "OGN-253", "OGN-027")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(46))
        draven = rules._new_unit(state, "SFD-020-221", 0, 0, exhausted=False)
        state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        rules._settle_battle(state, random.Random(47))
        self.assertTrue(any(gear["code"] == "SFD-T03" for gear in state["players"][0]["gear"]))

        state = rules.initial_state(random.Random(48))
        draven = rules._new_unit(state, "SFD-020-221", 0, 0, exhausted=False)
        rules._new_unit(state, "OGN-003", 1, 0, exhausted=False)
        state["players"][0]["power"] = ["fury"]
        state.update(phase="showdown", actor=0, focus=0, passes=0,
                     battle={"field": 0, "attacker": 0, "combat": True})
        rules._close_showdown(state, random.Random(49))
        rules.apply(state, Action.make("pass"), random.Random(50))
        rules.apply(state, Action.make("pass"), random.Random(51))
        self.assertEqual(state["phase"], "optional")
        optional = state["optional"][0]["id"]
        rules.apply(state, Action.make("optional_effect", optional=optional, accept=True), random.Random(52))
        self.assertEqual(draven["temporary"], 2)
        self.assertEqual(state["players"][0]["power"], [])

    def test_entry_ready_and_static_keywords_use_common_unit_path(self):
        deck = legal_deck("SFD-006-221", "OGN-247", "OGN-039")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(4))
        uid = move_code_to_hand(state, 0, "SFD-006-221")
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 3
        state["players"][0]["power"] = ["fury"] * 3
        payment = next(action for action in rules.legal_actions(state)
                       if action.kind == "play_unit" and __import__("json").loads(action.arguments)["card"] == uid)
        rules.apply(state, payment, random.Random(5))
        unit = next(unit for unit in state["units"] if unit["card"] == uid)
        self.assertFalse(unit["exhausted"])

        self.assertEqual(rules._deflect(state, unit), 0)

    def test_assault_ganking_tank_are_declarative_static_hooks(self):
        for code, legend, champion, keyword in (
                ("SFD-037-221", "OGN-257", "OGN-151", "deflect"),
                ("SFD-096-221", "OGN-249", "OGN-158", "ganking"),
                ("SFD-156-221", "OGN-253", "OGN-243", "assault_2"),
                ("SFD-176-221", "OGN-253", "OGN-243", "tank")):
            deck = legal_deck(code, legend, champion)
            rules = SpiritforgedRules([deck, deck])
            state = rules.initial_state(random.Random(7))
            uid = move_code_to_hand(state, 0, code)
            unit = rules._new_unit(state, code, 0, 0, card=uid, exhausted=True)
            self.assertIn(keyword, state["units"][-1].get("static_keywords", [])
                          or rules.card_registry.get(code).static_keywords)
            if keyword == "deflect":
                self.assertEqual(rules._deflect(state, unit), 1)
            elif keyword == "ganking":
                self.assertTrue(rules._ganking(state, unit))
            elif keyword == "assault_2":
                self.assertEqual(unit["assault"], 2)
            elif keyword == "tank":
                self.assertTrue(rules._tank(unit))

    def test_reaction_draw_three_is_a_registered_chain_effect(self):
        deck = legal_deck("SFD-087-221", "OGN-263", "OGN-121")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(9))
        card = move_code_to_hand(state, 0, "SFD-087-221")
        state["phase"], state["actor"] = "chain", 0
        state["players"][0]["energy"] = 2
        state["players"][0]["power"] = []
        actions = rules.legal_actions(state)
        play = next(action for action in actions if action.kind == "play_spell"
                    and __import__("json").loads(action.arguments)["card"] == card)
        rules.apply(state, play, random.Random(10))
        self.assertEqual(state["phase"], "chain")
        rules.apply(state, Action.make("pass"), random.Random(11))
        rules.apply(state, Action.make("pass"), random.Random(12))
        self.assertEqual(len(state["players"][0]["hand"]), 6)

    def test_resource_seal_reuses_the_existing_gear_resource_path(self):
        deck = legal_deck("SFD-222-221", "OGN-247", "OGN-039")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(13))
        card = move_code_to_hand(state, 0, "SFD-222-221")
        state["phase"], state["actor"] = "main", 0
        actions = rules.legal_actions(state)
        play = next(action for action in actions if action.kind == "play_gear"
                    and __import__("json").loads(action.arguments)["card"] == card)
        rules.apply(state, play, random.Random(14))
        gear = next(gear for gear in state["players"][0]["gear"] if gear["card"] == card)
        resource = next(action for action in rules.legal_actions(state)
                        if action.kind == "gear_resource"
                        and __import__("json").loads(action.arguments)["gear"] == gear["id"])
        rules.apply(state, resource, random.Random(15))
        self.assertEqual(state["players"][0]["power"][-1], "fury")
        self.assertTrue(gear["exhausted"])

    def test_registry_entry_and_move_hooks_are_executable(self):
        deck = legal_deck("SFD-094-221", "OGN-267", "OGN-162")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(20))
        card = move_code_to_hand(state, 0, "SFD-094-221")
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 20
        state["players"][0]["power"] = ["body"] * 20
        rules._new_unit(state, "OGN-001", 0, "base:0", exhausted=False)
        action = next(a for a in rules.legal_actions(state)
                      if a.kind == "play_unit"
                      and __import__("json").loads(a.arguments)["card"] == card)
        rules.apply(state, action, random.Random(21))
        unit = next(unit for unit in state["units"] if unit["card"] == card)
        self.assertFalse(unit["exhausted"])

        before = len(state["players"][0]["hand"])
        mover = rules._new_unit(state, "SFD-048-221", 0, "base:0", exhausted=False)
        state["fields"][0]["controller"] = 0
        rules._resolve_move(state, [mover], 0, 0, random.Random(22))
        self.assertEqual(len(state["players"][0]["hand"]), before + 1)

    def test_registry_deathknell_and_spell_hooks(self):
        deck = legal_deck("SFD-106-221", "OGN-267", "OGN-162")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(23))
        before = len(state["players"][0]["hand"])
        lonely = rules._new_unit(state, "SFD-036-221", 0, 0, exhausted=False)
        lonely["damage"] = rules.might(state, lonely)
        rules._cleanup(state, random.Random(24))
        self.assertEqual(len(state["players"][0]["hand"]), before + 1)

        spell = move_code_to_hand(state, 0, "SFD-106-221")
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 3
        state["players"][0]["power"] = ["body"] * 3
        rules._new_unit(state, "OGN-001", 0, "base:0", exhausted=False)
        draw_before = len(state["players"][0]["hand"])
        play = next(a for a in rules.legal_actions(state)
                    if a.kind == "play_spell"
                    and __import__("json").loads(a.arguments)["card"] == spell)
        rules.apply(state, play, random.Random(25))
        rules.apply(state, Action.make("pass"), random.Random(26))
        rules.apply(state, Action.make("pass"), random.Random(27))
        # The spell leaves hand and draws one card, so the net hand size is
        # unchanged while the draw hook has still consumed the top card.
        self.assertEqual(len(state["players"][0]["hand"]), draw_before)

    def test_registered_targeted_spells_use_shared_target_window(self):
        for code, legend, champion, target_scope, expected in (
                ("SFD-001-221", "OGN-247", "OGN-039", "friendly_field_unit", 2),
                ("SFD-097-221", "OGN-267", "OGN-162", "any_unit", 5),
        ):
            deck = legal_deck(code, legend, champion)
            rules = SpiritforgedRules([deck, deck])
            state = rules.initial_state(random.Random(31))
            card = move_code_to_hand(state, 0, code)
            target = rules._new_unit(state, "OGN-001", 0, 0, exhausted=False)
            if target_scope == "friendly_field_unit":
                rules._new_unit(state, "OGN-001", 1, 0, exhausted=False)
            state["phase"], state["actor"] = "main", 0
            state["players"][0]["energy"] = 5
            state["players"][0]["power"] = list(rules.cards[code]["domains"]) * 5
            play = next(action for action in rules.legal_actions(state)
                        if action.kind == "play_spell_targeted"
                        and __import__("json").loads(action.arguments)["card"] == card)
            rules.apply(state, play, random.Random(32))
            choose = next(action for action in rules.legal_actions(state)
                          if action.kind == "choose_target"
                          and __import__("json").loads(action.arguments)["target"] == target["id"])
            rules.apply(state, choose, random.Random(33))
            rules.apply(state, Action.make("pass"), random.Random(34))
            rules.apply(state, Action.make("pass"), random.Random(35))
            self.assertEqual(target["temporary"], expected)

    def test_defiant_dance_requires_two_distinct_clicked_targets(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(447))
        card = "p0:test-defiant-dance"
        state["cards"][card] = {"code": "SFD-196-221", "owner": 0}
        state["players"][0]["hand"].append(card)
        first = rules._new_unit(state, "OGN-001", 0, "base:0", exhausted=False)
        second = rules._new_unit(state, "OGN-001", 1, "base:1", exhausted=False)
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 5
        state["players"][0]["power"] = ["calm", "chaos"] * 5
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == card)
        args = __import__("json").loads(play.arguments)
        self.assertEqual(args["target_min"], 2)
        self.assertEqual(args["target_max"], 2)
        self.assertIn(first["id"], args["target_candidates"])
        self.assertIn(second["id"], args["target_candidates"])
        rules.apply(state, play, random.Random(448))
        rules.apply(state, Action.make("choose_target", target=first["id"]), random.Random(449))
        self.assertEqual(state["decision"]["selected"], [first["id"]])
        with self.assertRaises(ValueError):
            rules.apply(state, Action.make("choose_target", target=first["id"]), random.Random(450))
        rules.apply(state, Action.make("choose_target", target=second["id"]), random.Random(451))
        rules.apply(state, Action.make("confirm_targets"), random.Random(452))
        rules.apply(state, Action.make("pass"), random.Random(453))
        rules.apply(state, Action.make("pass"), random.Random(454))
        self.assertEqual(first["temporary"], 2)
        self.assertEqual(second["temporary"], -2)

    def test_counter_strike_marks_target_and_prevents_next_damage(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(455))
        card = "p0:test-counter-strike"
        state["cards"][card] = {"code": "SFD-194-221", "owner": 0}
        state["players"][0]["hand"].append(card)
        target = rules._new_unit(state, "OGN-001", 0, "base:0", exhausted=False)
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 5
        state["players"][0]["power"] = ["body"] * 5
        before_draw = len(state["players"][0]["hand"])
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == card)
        rules.apply(state, play, random.Random(456))
        rules.apply(state, Action.make("choose_target", target=target["id"]), random.Random(457))
        rules.apply(state, Action.make("pass"), random.Random(458))
        rules.apply(state, Action.make("pass"), random.Random(459))
        self.assertEqual(target["prevent_next_damage"], 1)
        self.assertEqual(len(state["players"][0]["hand"]), before_draw)
        rules._deal_damage(state, target, 3)
        self.assertEqual(target["damage"], 0)
        self.assertEqual(target["prevent_next_damage"], 0)
        rules._deal_damage(state, target, 3)
        self.assertEqual(target["damage"], 3)

    def test_blast_corps_optional_payment_opens_entry_damage_target(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(460))
        card = "p0:test-blast-corps"
        state["cards"][card] = {"code": "SFD-013-221", "owner": 0}
        state["players"][0]["hand"].append(card)
        target = rules._new_unit(state, "OGN-027", 1, 0, exhausted=False)
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["fury"] * 10
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == card
                    and __import__("json").loads(action.arguments)["additional_cost"])
        rules.apply(state, play, random.Random(461))
        self.assertEqual(state["decision"]["targets"], [target["id"]])
        rules.apply(state, Action.make("choose_target", target=target["id"]), random.Random(462))
        rules.apply(state, Action.make("pass"), random.Random(463))
        rules.apply(state, Action.make("pass"), random.Random(464))
        self.assertEqual(target["damage"], 2)

    def test_frostcoat_optional_power_payment_uses_shared_target_window(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(465))
        card = "p0:test-frostcoat-cub"
        state["cards"][card] = {"code": "SFD-067-221", "owner": 0}
        state["players"][0]["hand"].append(card)
        target = rules._new_unit(state, "OGN-027", 1, "base:1", exhausted=False)
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["mind"] * 10
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == card
                    and __import__("json").loads(action.arguments)["additional_cost"])
        args = __import__("json").loads(play.arguments)
        self.assertEqual(len(args["payment"]), 4)
        rules.apply(state, play, random.Random(466))
        self.assertIn(target["id"], state["decision"]["targets"])
        rules.apply(state, Action.make("choose_target", target=target["id"]), random.Random(467))
        rules.apply(state, Action.make("pass"), random.Random(468))
        rules.apply(state, Action.make("pass"), random.Random(469))
        self.assertEqual(target["temporary"], -2)

    def test_resource_conversion_gears_use_amount_windows(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(470))
        anomaly = "p0:test-hextech-anomaly"
        state["cards"][anomaly] = {"code": "SFD-083-221", "owner": 0}
        state["players"][0]["gear"].append({
            "id": anomaly, "card": anomaly, "code": "SFD-083-221", "owner": 0,
            "card_owner": 0, "location": "base:0", "exhausted": False,
            "temporary": False,
        })
        state.update(phase="main", actor=0)
        state["players"][0]["power"] = ["any", "any"]
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "gear_activate"
                      and __import__("json").loads(action.arguments)["gear"] == anomaly
                      and __import__("json").loads(action.arguments)["amount"] == 2)
        rules.apply(state, action, random.Random(471))
        self.assertEqual(state["players"][0]["energy"], 2)
        self.assertEqual(state["players"][0]["power"], [])
        self.assertTrue(state["players"][0]["gear"][0]["exhausted"])

        henge = "p0:test-ancient-henge"
        state["cards"][henge] = {"code": "SFD-117-221", "owner": 0}
        state["players"][0]["gear"].append({
            "id": henge, "card": henge, "code": "SFD-117-221", "owner": 0,
            "card_owner": 0, "location": "base:0", "exhausted": False,
            "temporary": False,
        })
        state["players"][0]["energy"] = 3
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "gear_activate"
                      and __import__("json").loads(action.arguments)["gear"] == henge
                      and __import__("json").loads(action.arguments)["amount"] == 3)
        rules.apply(state, action, random.Random(472))
        self.assertEqual(state["players"][0]["energy"], 0)
        self.assertEqual(state["players"][0]["power"], ["any", "any", "any"])

    def test_not_so_fast_uses_registered_chain_target_filter(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(473))
        counter = "p0:test-not-so-fast"
        state["cards"][counter] = {"code": "SFD-045-221", "owner": 0}
        state["players"][0]["hand"].append(counter)
        target_unit = rules._new_unit(state, "OGN-027", 1, "base:1", exhausted=False)
        state["chain"] = [{"effect": "spell", "owner": 1, "card": None,
                            "code": "OGN-005", "targets": [target_unit["id"]]}]
        state.update(phase="chain", actor=0, passes=0, chain_return="main")
        state["players"][0]["energy"] = 3
        state["players"][0]["power"] = ["calm"] * 3
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_counter"
                    and __import__("json").loads(action.arguments)["card"] == counter)
        self.assertEqual(__import__("json").loads(play.arguments)["targets"], ["chain:0"])
        rules.apply(state, play, random.Random(474))
        choose = next(action for action in rules.legal_actions(state)
                      if action.kind == "choose_chain_target")
        rules.apply(state, choose, random.Random(475))
        rules.apply(state, Action.make("pass"), random.Random(476))
        rules.apply(state, Action.make("pass"), random.Random(477))
        self.assertEqual(state["chain"], [])
        self.assertIn(counter, state["players"][0]["trash"])

    def test_rengar_reaction_is_restricted_to_the_attacked_battlefield(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(478))
        card = "p0:test-rengar"
        state["cards"][card] = {"code": "SFD-025-221", "owner": 0}
        state["players"][0]["hand"].append(card)
        enemy = rules._new_unit(state, "OGN-027", 1, 0, exhausted=False)
        state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        state.update(phase="showdown", actor=0, passes=0)
        state["players"][0]["energy"] = 6
        state["players"][0]["power"] = ["fury"] * 6
        actions = [action for action in rules.legal_actions(state)
                   if action.kind == "play_unit"
                   and __import__("json").loads(action.arguments)["card"] == card]
        self.assertGreater(len(actions), 0)
        args = __import__("json").loads(actions[0].arguments)
        self.assertTrue(all(__import__("json").loads(action.arguments)["location"] == 0
                            for action in actions))
        rules.apply(state, actions[0], random.Random(479))
        rengar = next(unit for unit in state["units"] if unit["id"] != enemy["id"]
                      and unit["code"] == "SFD-025-221")
        self.assertEqual(rengar["assault"], 2)
        self.assertEqual(rules.might(state, rengar), 3)

    def test_lucian_merciless_readies_on_first_conquer_each_turn(self):
        deck = legal_deck("OGN-124", "OGN-267", "OGN-193")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(480))
        lucian = rules._new_unit(state, "SFD-113-221", 0, 0, exhausted=True)
        state["fields"][0]["controller"] = 0
        state.update(phase="main", actor=0)
        rules._score(state, 0, 0, "conquer", random.Random(481))
        self.assertFalse(lucian["exhausted"])
        self.assertEqual(lucian.get("conquer_ready_turn"), state["turn"])
        lucian["exhausted"] = True
        lucian["location"] = 1
        state["fields"][1]["controller"] = 0
        rules._score(state, 0, 1, "conquer", random.Random(482))
        self.assertTrue(lucian["exhausted"])
        state["turn"] += 1
        lucian["location"] = 0
        state["scored"][0] = []
        rules._score(state, 0, 0, "conquer", random.Random(483))
        self.assertFalse(lucian["exhausted"])

    def test_registered_gear_return_and_gold_deathknell(self):
        deck = legal_deck("SFD-135-221", "OGN-267", "OGN-162")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(36))
        card = move_code_to_hand(state, 0, "SFD-135-221")
        gear = {"id": "gear:test", "card": None, "code": "OGN-040",
                "owner": 1, "card_owner": 1, "location": "base:1",
                "exhausted": False, "temporary": False}
        state["players"][1]["gear"].append(gear)
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 3
        state["players"][0]["power"] = ["chaos"] * 3
        play = next(action for action in rules.legal_actions(state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == card)
        rules.apply(state, play, random.Random(37))
        choose = next(action for action in rules.legal_actions(state)
                      if action.kind == "choose_target"
                      and __import__("json").loads(action.arguments)["target"] == "gear:test")
        rules.apply(state, choose, random.Random(38))
        rules.apply(state, Action.make("pass"), random.Random(39))
        rules.apply(state, Action.make("pass"), random.Random(40))
        self.assertNotIn(gear, state["players"][1]["gear"])

        detonate_deck = legal_deck("SFD-005-221", "OGN-247", "OGN-039")
        detonate_rules = SpiritforgedRules([detonate_deck, detonate_deck])
        detonate_state = detonate_rules.initial_state(random.Random(43))
        detonate_card = move_code_to_hand(detonate_state, 0, "SFD-005-221")
        detonate_gear = {"id": "gear:detonate", "card": None, "code": "OGN-040",
                         "owner": 1, "card_owner": 1, "location": "base:1",
                         "exhausted": False, "temporary": False}
        detonate_state["players"][1]["gear"].append(detonate_gear)
        before_draw = len(detonate_state["players"][1]["hand"])
        detonate_state["phase"], detonate_state["actor"] = "main", 0
        detonate_state["players"][0]["energy"] = 3
        detonate_state["players"][0]["power"] = ["fury"] * 3
        play = next(action for action in detonate_rules.legal_actions(detonate_state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == detonate_card)
        detonate_rules.apply(detonate_state, play, random.Random(44))
        choose = next(action for action in detonate_rules.legal_actions(detonate_state)
                      if action.kind == "choose_target"
                      and __import__("json").loads(action.arguments)["target"] == "gear:detonate")
        detonate_rules.apply(detonate_state, choose, random.Random(45))
        detonate_rules.apply(detonate_state, Action.make("pass"), random.Random(46))
        detonate_rules.apply(detonate_state, Action.make("pass"), random.Random(47))
        self.assertNotIn(detonate_gear, detonate_state["players"][1]["gear"])
        self.assertEqual(len(detonate_state["players"][1]["hand"]), before_draw + 2)

        order_deck = legal_deck("SFD-155-221", "OGN-253", "OGN-243")
        order_rules = SpiritforgedRules([order_deck, order_deck])
        order_state = order_rules.initial_state(random.Random(41))
        dead = order_rules._new_unit(order_state, "SFD-155-221", 0, 0, exhausted=False)
        dead["damage"] = order_rules.might(order_state, dead)
        order_rules._cleanup(order_state, random.Random(42))
        gold = [gear for gear in order_state["players"][0]["gear"]
                if gear["code"] == "SFD-T03"]
        self.assertEqual(len(gold), 1)
        self.assertTrue(gold[0]["exhausted"])

    def test_registered_unit_entry_buff_might_and_move_hooks(self):
        deck = legal_deck("SFD-047-221", "OGN-255", "OGN-066")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(48))
        ancestor = rules._new_unit(state, "SFD-047-221", 0, "base:0", exhausted=True)
        rules._apply_buff(state, ancestor)
        self.assertFalse(ancestor["exhausted"])

        entry_deck = legal_deck("SFD-072-221", "OGN-247", "OGN-039")
        entry_rules = SpiritforgedRules([entry_deck, entry_deck])
        entry_state = entry_rules.initial_state(random.Random(49))
        for index in range(2):
            entry_state["players"][0]["gear"].append({
                "id": f"gear:entry:{index}", "card": None, "code": "OGN-040",
                "owner": 0, "card_owner": 0, "location": "base:0",
                "exhausted": False, "temporary": False})
        self.assertTrue(entry_rules._entry_ready(entry_state, "SFD-072-221", 0))

        move_deck = legal_deck("SFD-130-221", "OGN-267", "OGN-162")
        move_rules = SpiritforgedRules([move_deck, move_deck])
        move_state = move_rules.initial_state(random.Random(50))
        move_state["fields"][0]["controller"] = 0
        hunter = move_rules._new_unit(move_state, "SFD-130-221", 0, "base:0", exhausted=False)
        move_rules._resolve_move(move_state, [hunter], 0, 0, random.Random(51))
        self.assertTrue(any(g["code"] == "SFD-T03" for g in move_state["players"][0]["gear"]))

        harpoon_deck = legal_deck("SFD-137-221", "OGN-267", "OGN-162")
        harpoon_rules = SpiritforgedRules([harpoon_deck, harpoon_deck])
        harpoon_state = harpoon_rules.initial_state(random.Random(52))
        harpoon_state["fields"][0]["controller"] = 0
        harpoon = harpoon_rules._new_unit(harpoon_state, "SFD-137-221", 0, 0, exhausted=False)
        harpoon_rules._resolve_move(harpoon_state, [harpoon], "base:0", 0, random.Random(53))
        self.assertEqual(harpoon["temporary"], 2)

        ramhound_deck = legal_deck("SFD-159-221", "OGN-253", "OGN-243")
        ramhound_rules = SpiritforgedRules([ramhound_deck, ramhound_deck])
        ramhound_state = ramhound_rules.initial_state(random.Random(54))
        ramhound = ramhound_rules._new_unit(ramhound_state, "SFD-159-221", 0, "base:0", exhausted=False)
        ally = ramhound_rules._new_unit(ramhound_state, "OGN-001", 0, "base:0", exhausted=False)
        self.assertEqual(ramhound_rules.might(ramhound_state, ramhound), 3)
        ramhound_state["units"].remove(ally)
        self.assertEqual(ramhound_rules.might(ramhound_state, ramhound), 2)

        mighty_deck = legal_deck("SFD-167-221", "OGN-253", "OGN-243")
        mighty_rules = SpiritforgedRules([mighty_deck, mighty_deck])
        mighty_state = mighty_rules.initial_state(random.Random(55))
        before = len(mighty_state["players"][0]["hand"])
        mighty = mighty_rules._new_unit(mighty_state, "SFD-167-221", 0, 0, exhausted=False)
        mighty["temporary"] = 3
        mighty["damage"] = mighty_rules.might(mighty_state, mighty)
        mighty_rules._cleanup(mighty_state, random.Random(56))
        self.assertEqual(len(mighty_state["players"][0]["hand"]), before + 2)

        dunebreaker_deck = legal_deck("SFD-027-221", "OGN-247", "OGN-039")
        dunebreaker_rules = SpiritforgedRules([dunebreaker_deck, dunebreaker_deck])
        dunebreaker_state = dunebreaker_rules.initial_state(random.Random(57))
        dunebreaker_state["players"][0]["hand"] = dunebreaker_state["players"][0]["hand"][:2]
        self.assertTrue(dunebreaker_rules._entry_ready(dunebreaker_state, "SFD-027-221", 0))
        holder = dunebreaker_rules._new_unit(dunebreaker_state, "SFD-027-221", 0, 0, exhausted=False)
        dunebreaker_state["fields"][0]["controller"] = 0
        before_hold_draw = len(dunebreaker_state["players"][0]["hand"])
        dunebreaker_rules._score(dunebreaker_state, 0, 0, "hold", random.Random(58))
        self.assertEqual(len(dunebreaker_state["players"][0]["hand"]), before_hold_draw + 2)

    def test_registered_entry_trigger_target_windows(self):
        engineer_deck = legal_deck("SFD-061-221", "OGN-255", "OGN-066")
        engineer_rules = SpiritforgedRules([engineer_deck, engineer_deck])
        engineer_state = engineer_rules.initial_state(random.Random(59))
        engineer_card = move_code_to_hand(engineer_state, 0, "SFD-061-221")
        gear_card = engineer_state["players"][0]["main"][-1]
        engineer_state["cards"][gear_card]["code"] = "OGN-040"
        engineer_state["players"][0]["main"].remove(gear_card)
        engineer_state["players"][0]["trash"].append(gear_card)
        engineer_state["phase"], engineer_state["actor"] = "main", 0
        engineer_state["players"][0]["energy"] = 10
        engineer_state["players"][0]["power"] = ["mind"] * 10
        play = next(action for action in engineer_rules.legal_actions(engineer_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == engineer_card)
        engineer_rules.apply(engineer_state, play, random.Random(60))
        choose = next(action for action in engineer_rules.legal_actions(engineer_state)
                      if action.kind == "choose_target"
                      and __import__("json").loads(action.arguments)["target"] == gear_card)
        engineer_rules.apply(engineer_state, choose, random.Random(61))
        engineer_rules.apply(engineer_state, Action.make("pass"), random.Random(62))
        engineer_rules.apply(engineer_state, Action.make("pass"), random.Random(63))
        self.assertIn(gear_card, engineer_state["players"][0]["hand"])

        bot_deck = legal_deck("SFD-062-221", "OGN-247", "OGN-039")
        bot_rules = SpiritforgedRules([bot_deck, bot_deck])
        bot_state = bot_rules.initial_state(random.Random(64))
        bot_card = move_code_to_hand(bot_state, 0, "SFD-062-221")
        mech = bot_rules._new_unit(bot_state, "OGN-088", 0, "base:0", exhausted=True)
        bot_state["phase"], bot_state["actor"] = "main", 0
        bot_state["players"][0]["energy"] = 10
        bot_state["players"][0]["power"] = ["mind"] * 10
        play = next(action for action in bot_rules.legal_actions(bot_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == bot_card)
        bot_rules.apply(bot_state, play, random.Random(65))
        choose = next(action for action in bot_rules.legal_actions(bot_state)
                      if action.kind == "choose_target"
                      and __import__("json").loads(action.arguments)["target"] == mech["id"])
        bot_rules.apply(bot_state, choose, random.Random(66))
        bot_rules.apply(bot_state, Action.make("pass"), random.Random(67))
        bot_rules.apply(bot_state, Action.make("pass"), random.Random(68))
        self.assertFalse(mech["exhausted"])

    def test_registered_gold_token_and_token_ready_hooks(self):
        hold_deck = legal_deck("SFD-152-221", "OGN-253", "OGN-243")
        hold_rules = SpiritforgedRules([hold_deck, hold_deck])
        hold_state = hold_rules.initial_state(random.Random(69))
        holder = hold_rules._new_unit(hold_state, "SFD-152-221", 0, 0, exhausted=False)
        hold_state["fields"][0]["controller"] = 0
        hold_rules._score(hold_state, 0, 0, "hold", random.Random(70))
        self.assertEqual(sum(g["code"] == "SFD-T03" for g in hold_state["players"][0]["gear"]), 2)

        ready_deck = legal_deck("SFD-171-221", "OGN-253", "OGN-243")
        ready_rules = SpiritforgedRules([ready_deck, ready_deck])
        ready_state = ready_rules.initial_state(random.Random(71))
        ready_rules._new_unit(ready_state, "SFD-171-221", 0, "base:0", exhausted=False)
        token = ready_rules._new_unit(ready_state, "OGN-273", 0, "base:0", exhausted=True)
        self.assertFalse(token["exhausted"])
        gold = ready_rules._play_gold_gear_token(ready_state, 0, exhausted=True)
        created = next(g for g in ready_state["players"][0]["gear"] if g["id"] == gold)
        self.assertFalse(created["exhausted"])

        trove_deck = legal_deck("SFD-174-221", "OGN-253", "OGN-243")
        trove_rules = SpiritforgedRules([trove_deck, trove_deck])
        trove_state = trove_rules.initial_state(random.Random(72))
        trove_card = move_code_to_hand(trove_state, 0, "SFD-174-221")
        trove_state["phase"], trove_state["actor"] = "main", 0
        trove_state["players"][0]["energy"] = 10
        trove_state["players"][0]["power"] = ["order"] * 10
        play = next(action for action in trove_rules.legal_actions(trove_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == trove_card)
        trove_rules.apply(trove_state, play, random.Random(73))
        trove_rules.apply(trove_state, Action.make("pass"), random.Random(74))
        trove_rules.apply(trove_state, Action.make("pass"), random.Random(75))
        self.assertEqual(sum(g["code"] == "SFD-T03" for g in trove_state["players"][0]["gear"]), 4)

    def test_registered_additional_cost_unit_uses_common_payment(self):
        deck = legal_deck("SFD-098-221", "OGN-267", "OGN-162")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(76))
        card = move_code_to_hand(state, 0, "SFD-098-221")
        state["phase"], state["actor"] = "main", 0
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["body"] * 10
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "play_unit"
                      and __import__("json").loads(action.arguments)["card"] == card
                      and __import__("json").loads(action.arguments)["additional_cost"])
        rules.apply(state, action, random.Random(77))
        unit = next(unit for unit in state["units"] if unit["card"] == card)
        self.assertEqual(unit["buff"], 1)

    def test_batch_optional_entry_windows_are_explicit(self):
        rake_deck = legal_deck("SFD-032-221", "OGN-255", "OGN-119")
        rake_rules = SpiritforgedRules([rake_deck, rake_deck])
        rake_state = rake_rules.initial_state(random.Random(80))
        rake_card = move_code_to_hand(rake_state, 0, "SFD-032-221")
        rake_state["players"][1]["gear"].append({
            "id": "gear:rake", "card": None, "code": "OGN-040", "owner": 1,
            "card_owner": 1, "location": "base:1", "exhausted": False,
            "temporary": False,
        })
        rake_state["phase"], rake_state["actor"] = "main", 0
        rake_state["players"][0]["energy"] = 10
        rake_state["players"][0]["power"] = ["calm"] * 10
        play = next(action for action in rake_rules.legal_actions(rake_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == rake_card)
        rake_rules.apply(rake_state, play, random.Random(81))
        rake_rules.apply(rake_state, Action.make("pass"), random.Random(82))
        rake_rules.apply(rake_state, Action.make("pass"), random.Random(83))
        optional = rake_state["optional"][0]
        self.assertEqual(optional["effect"], "kill_gear")
        rake_rules.apply(rake_state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(84))
        self.assertEqual(rake_state["decision"]["kind"], "target")
        rake_rules.apply(rake_state, Action.make("choose_target", target="gear:rake"), random.Random(85))
        self.assertFalse(any(gear["id"] == "gear:rake" for row in rake_state["players"] for gear in row["gear"]))
        self.assertEqual(rake_state["phase"], "main")

        captain_deck = legal_deck("SFD-091-221", "OGN-257", "OGN-151")
        captain_rules = SpiritforgedRules([captain_deck, captain_deck])
        captain_state = captain_rules.initial_state(random.Random(86))
        captain_card = move_code_to_hand(captain_state, 0, "SFD-091-221")
        captain_state["phase"], captain_state["actor"] = "main", 0
        captain_state["players"][0]["energy"] = 10
        captain_state["players"][0]["power"] = ["body"] * 10
        play = next(action for action in captain_rules.legal_actions(captain_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == captain_card)
        captain_rules.apply(captain_state, play, random.Random(87))
        captain_rules.apply(captain_state, Action.make("pass"), random.Random(88))
        captain_rules.apply(captain_state, Action.make("pass"), random.Random(89))
        optional = captain_state["optional"][0]
        captain_rules.apply(captain_state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(90))
        self.assertEqual(set(captain_state["decision"]["options"]), {"draw", "buff"})
        captain_rules.apply(captain_state, Action.make("choose_option", option="buff"), random.Random(91))
        unit = next(unit for unit in captain_state["units"] if unit["card"] == captain_card)
        self.assertEqual(unit["buff"], 1)

    def test_batch_entry_tokens_discard_and_targeted_spell(self):
        ezreal_deck = legal_deck("SFD-149-221", "OGN-267", "OGN-162")
        ezreal_rules = SpiritforgedRules([ezreal_deck, ezreal_deck])
        ezreal_state = ezreal_rules.initial_state(random.Random(92))
        ezreal_card = move_code_to_hand(ezreal_state, 0, "SFD-149-221")
        ezreal_state["phase"], ezreal_state["actor"] = "main", 0
        ezreal_state["players"][0]["energy"] = 10
        ezreal_state["players"][0]["power"] = ["chaos"] * 10
        before = len(ezreal_state["players"][0]["hand"])
        play = next(action for action in ezreal_rules.legal_actions(ezreal_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == ezreal_card)
        ezreal_rules.apply(ezreal_state, play, random.Random(93))
        ezreal_rules.apply(ezreal_state, Action.make("pass"), random.Random(94))
        ezreal_rules.apply(ezreal_state, Action.make("pass"), random.Random(95))
        self.assertTrue(ezreal_state["decision"].get("discard_one_draw_two"))
        discard = ezreal_state["players"][0]["hand"][0]
        ezreal_rules.apply(ezreal_state, Action.make("discard_card", card=discard), random.Random(96))
        self.assertEqual(len(ezreal_state["players"][0]["hand"]), before)
        self.assertEqual(ezreal_state["phase"], "main")

        guard_deck = legal_deck("SFD-157-221", "OGN-253", "OGN-243")
        guard_rules = SpiritforgedRules([guard_deck, guard_deck])
        guard_state = guard_rules.initial_state(random.Random(97))
        guard_card = move_code_to_hand(guard_state, 0, "SFD-157-221")
        guard_state["phase"], guard_state["actor"] = "main", 0
        guard_state["players"][0]["energy"] = 10
        guard_state["players"][0]["power"] = ["order"] * 10
        play = next(action for action in guard_rules.legal_actions(guard_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == guard_card)
        guard_rules.apply(guard_state, play, random.Random(98))
        guard_rules.apply(guard_state, Action.make("pass"), random.Random(99))
        guard_rules.apply(guard_state, Action.make("pass"), random.Random(100))
        self.assertEqual(sum(unit["code"] == "SFD-T04" for unit in guard_state["units"]), 1)

        blood_deck = legal_deck("SFD-162-221", "OGN-253", "OGN-243")
        blood_rules = SpiritforgedRules([blood_deck, blood_deck])
        blood_state = blood_rules.initial_state(random.Random(101))
        blood_card = move_code_to_hand(blood_state, 0, "SFD-162-221")
        target = blood_rules._new_unit(blood_state, "OGN-096", 1, 0, exhausted=False)
        blood_state["phase"], blood_state["actor"] = "main", 0
        blood_state["players"][0]["energy"] = 10
        blood_state["players"][0]["power"] = ["order"] * 10
        play = next(action for action in blood_rules.legal_actions(blood_state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == blood_card)
        blood_rules.apply(blood_state, play, random.Random(102))
        blood_rules.apply(blood_state, Action.make("choose_target", target=target["id"]), random.Random(103))
        blood_rules.apply(blood_state, Action.make("pass"), random.Random(104))
        blood_rules.apply(blood_state, Action.make("pass"), random.Random(105))
        self.assertNotIn(target, blood_state["units"])
        self.assertEqual(sum(gear["code"] == "SFD-T03" for gear in blood_state["players"][0]["gear"]), 1)

    def test_batch_move_and_static_hooks_share_common_paths(self):
        ribbon_deck = legal_deck("SFD-038-221", "OGN-255", "OGN-119")
        ribbon_rules = SpiritforgedRules([ribbon_deck, ribbon_deck])
        ribbon_state = ribbon_rules.initial_state(random.Random(106))
        ribbon = ribbon_rules._new_unit(ribbon_state, "SFD-038-221", 0, "base:0", exhausted=False)
        ally = ribbon_rules._new_unit(ribbon_state, "OGN-001", 0, 0, exhausted=False)
        ribbon_state["fields"][0]["controller"] = 0
        ribbon_rules._resolve_move(ribbon_state, [ribbon], 0, 0, random.Random(107))
        choose = next(action for action in ribbon_rules.legal_actions(ribbon_state)
                      if action.kind == "choose_target" and
                      __import__("json").loads(action.arguments)["target"] == ally["id"])
        ribbon_rules.apply(ribbon_state, choose, random.Random(108))
        ribbon_rules.apply(ribbon_state, Action.make("pass"), random.Random(109))
        ribbon_rules.apply(ribbon_state, Action.make("pass"), random.Random(110))
        self.assertEqual(ally["buff"], 1)

        recruit_deck = legal_deck("SFD-179-221", "OGN-253", "OGN-243")
        recruit_rules = SpiritforgedRules([recruit_deck, recruit_deck])
        recruit_state = recruit_rules.initial_state(random.Random(109))
        mover = recruit_rules._new_unit(recruit_state, "SFD-179-221", 0, "base:0", exhausted=False)
        recruit_state["fields"][0]["controller"] = 0
        recruit_rules._resolve_move(recruit_state, [mover], 0, 0, random.Random(110))
        self.assertEqual(sum(unit["code"] == "OGN-273" for unit in recruit_state["units"]), 3)

        ready_deck = legal_deck("SFD-071-221", "OGN-247", "OGN-039")
        ready_rules = SpiritforgedRules([ready_deck, ready_deck])
        ready_state = ready_rules.initial_state(random.Random(111))
        ready_rules._new_unit(ready_state, "OGN-067", 0, "base:0", exhausted=False)
        self.assertTrue(ready_rules._entry_ready(ready_state, "SFD-071-221", 0))
        breakneck = ready_rules._new_unit(ready_state, "SFD-071-221", 0, "base:0", exhausted=True)
        ally_mech = ready_rules._new_unit(ready_state, "OGN-088", 0, "base:0", exhausted=True)
        self.assertTrue(ready_rules._ganking(ready_state, breakneck))
        self.assertEqual(ready_rules._deflect(ready_state, breakneck), 1)
        self.assertTrue(ready_rules._ganking(ready_state, ally_mech))
        self.assertEqual(ready_rules._deflect(ready_state, ally_mech), 1)

    def test_batch_hold_return_is_optional_and_targeted(self):
        deck = legal_deck("SFD-035-221", "OGN-255", "OGN-119")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(112))
        state["phase"] = "main"
        rules._new_unit(state, "SFD-035-221", 0, 0, exhausted=False)
        state["fields"][0]["controller"] = 0
        trash_card = state["players"][0]["main"].pop()
        state["cards"][trash_card]["code"] = "OGN-040"
        state["players"][0]["trash"].append(trash_card)
        rules._score(state, 0, 0, "hold", random.Random(113))
        self.assertEqual(state["phase"], "optional")
        optional = state["optional"][0]
        rules.apply(state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(114))
        self.assertIn(trash_card, state["decision"]["targets"])
        rules.apply(state, Action.make("choose_target", target=trash_card), random.Random(115))
        self.assertIn(trash_card, state["players"][0]["hand"])

    def test_batch_vision_conquer_and_gear_listener_hooks(self):
        vision_deck = legal_deck("SFD-065-221", "OGN-247", "OGN-039")
        vision_rules = SpiritforgedRules([vision_deck, vision_deck])
        vision_state = vision_rules.initial_state(random.Random(116))
        vision_card = move_code_to_hand(vision_state, 0, "SFD-065-221")
        vision_state["phase"], vision_state["actor"] = "main", 0
        vision_state["players"][0]["energy"] = 10
        vision_state["players"][0]["power"] = ["mind"] * 10
        play = next(action for action in vision_rules.legal_actions(vision_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == vision_card)
        vision_rules.apply(vision_state, play, random.Random(117))
        vision_rules.apply(vision_state, Action.make("pass"), random.Random(118))
        vision_rules.apply(vision_state, Action.make("pass"), random.Random(119))
        self.assertEqual(vision_state["decision"]["kind"], "predict")

        conquer_deck = legal_deck("SFD-069-221", "OGN-247", "OGN-039")
        conquer_rules = SpiritforgedRules([conquer_deck, conquer_deck])
        conquer_state = conquer_rules.initial_state(random.Random(120))
        conquer_rules._new_unit(conquer_state, "SFD-069-221", 0, 0, exhausted=False)
        before_gold = sum(g["code"] == "SFD-T03" for g in conquer_state["players"][0]["gear"])
        conquer_rules._score(conquer_state, 0, 0, "conquer", random.Random(121))
        after_gold = sum(g["code"] == "SFD-T03" for g in conquer_state["players"][0]["gear"])
        self.assertEqual(after_gold, before_gold + 1)

        pickpocket_deck = legal_deck("SFD-074-221", "OGN-247", "OGN-039")
        pickpocket_rules = SpiritforgedRules([pickpocket_deck, pickpocket_deck])
        pickpocket_state = pickpocket_rules.initial_state(random.Random(122))
        pickpocket_state["phase"], pickpocket_state["actor"] = "main", 0
        pickpocket_state["players"][1]["gear"].append({
            "id": "gear:cheap", "card": None, "code": "OGN-040", "owner": 1,
            "card_owner": 1, "location": "base:1", "exhausted": False,
            "temporary": False,
        })
        source = pickpocket_rules._new_unit(pickpocket_state, "SFD-074-221", 0, 0, exhausted=False)
        pickpocket_rules._effect_optional_kill_cheap_gear(
            pickpocket_state, {"owner": 0, "source": source["id"]}, random.Random(123))
        optional = pickpocket_state["optional"][0]
        pickpocket_rules.apply(
            pickpocket_state,
            Action.make("optional_effect", optional=optional["id"], accept=True),
            random.Random(124))
        self.assertEqual(pickpocket_state["decision"]["targets"], ["gear:cheap"])
        pickpocket_rules.apply(
            pickpocket_state, Action.make("choose_target", target="gear:cheap"), random.Random(125))
        self.assertEqual(sum(g["code"] == "SFD-T03" for g in pickpocket_state["players"][0]["gear"]), 1)

        prize_deck = legal_deck("SFD-075-221", "OGN-247", "OGN-039")
        prize_rules = SpiritforgedRules([prize_deck, prize_deck])
        prize_state = prize_rules.initial_state(random.Random(126))
        prize = prize_rules._new_unit(prize_state, "SFD-075-221", 0, "base:0", exhausted=False)
        prize_state["players"][0]["gear"].append({
            "id": "gear:prize", "card": None, "code": "OGN-040", "owner": 0,
            "card_owner": 0, "location": "base:0", "exhausted": False,
            "temporary": False,
        })
        prize_state["phase"], prize_state["actor"] = "main", 0
        action = next(action for action in prize_rules.legal_actions(prize_state)
                      if action.kind == "gear_resource"
                      and __import__("json").loads(action.arguments)["gear"] == "gear:prize")
        prize_rules.apply(prize_state, action, random.Random(127))
        self.assertEqual(prize["temporary"], 1)

    def test_batch_registered_token_and_simple_targeted_spells(self):
        soldier_deck = legal_deck("SFD-031-221", "OGN-255", "OGN-119")
        soldier_rules = SpiritforgedRules([soldier_deck, soldier_deck])
        soldier_state = soldier_rules.initial_state(random.Random(128))
        soldier_card = move_code_to_hand(soldier_state, 0, "SFD-031-221")
        soldier_state["phase"], soldier_state["actor"] = "main", 0
        soldier_state["players"][0]["energy"] = 10
        soldier_state["players"][0]["power"] = ["fury"] * 10
        play = next(action for action in soldier_rules.legal_actions(soldier_state)
                    if action.kind == "play_spell"
                    and __import__("json").loads(action.arguments)["card"] == soldier_card)
        soldier_rules.apply(soldier_state, play, random.Random(129))
        soldier_rules.apply(soldier_state, Action.make("pass"), random.Random(130))
        soldier_rules.apply(soldier_state, Action.make("pass"), random.Random(131))
        self.assertEqual(sum(unit["code"] == "SFD-T04" for unit in soldier_state["units"]), 1)

        for code, expected, legend in (("SFD-034-221", 2, "OGN-255"),
                                       ("SFD-066-221", -2, "OGN-247")):
            deck = legal_deck(code, legend, "OGN-119" if legend == "OGN-255" else "OGN-039")
            rules = SpiritforgedRules([deck, deck])
            state = rules.initial_state(random.Random(132 if expected > 0 else 133))
            card = move_code_to_hand(state, 0, code)
            target = rules._new_unit(state, "OGN-001", 1, 0, exhausted=False)
            state["phase"], state["actor"] = "main", 0
            state["players"][0]["energy"] = 10
            state["players"][0]["power"] = ["calm" if expected > 0 else "mind"] * 10
            play = next(action for action in rules.legal_actions(state)
                        if action.kind == "play_spell_targeted"
                        and __import__("json").loads(action.arguments)["card"] == card)
            rules.apply(state, play, random.Random(134))
            rules.apply(state, Action.make("choose_target", target=target["id"]), random.Random(135))
            rules.apply(state, Action.make("pass"), random.Random(136))
            rules.apply(state, Action.make("pass"), random.Random(137))
            self.assertEqual(target["temporary"], expected)

        surge_deck = legal_deck("SFD-076-221", "OGN-247", "OGN-039")
        surge_rules = SpiritforgedRules([surge_deck, surge_deck])
        surge_state = surge_rules.initial_state(random.Random(138))
        surge_card = move_code_to_hand(surge_state, 0, "SFD-076-221")
        mech = surge_rules._new_unit(surge_state, "OGN-088", 0, "base:0", exhausted=False)
        before = len(surge_state["players"][0]["hand"])
        surge_state["phase"], surge_state["actor"] = "main", 0
        surge_state["players"][0]["energy"] = 2
        surge_state["players"][0]["power"] = ["mind"] * 2
        play = next(action for action in surge_rules.legal_actions(surge_state)
                    if action.kind == "play_spell"
                    and __import__("json").loads(action.arguments)["card"] == surge_card)
        surge_rules.apply(surge_state, play, random.Random(139))
        surge_rules.apply(surge_state, Action.make("pass"), random.Random(140))
        surge_rules.apply(surge_state, Action.make("pass"), random.Random(141))
        self.assertEqual(sum(unit["code"] == "SFD-T05" for unit in surge_state["units"]), 1)
        self.assertEqual(len(surge_state["players"][0]["hand"]), before)
        self.assertIn(mech, surge_state["units"])

    def test_batch_hidden_optional_resources_and_arise_selection(self):
        guards_deck = legal_deck("SFD-154-221", "OGN-253", "OGN-243")
        guards_rules = SpiritforgedRules([guards_deck, guards_deck])
        guards_state = guards_rules.initial_state(random.Random(201))
        guards_card = move_code_to_hand(guards_state, 0, "SFD-154-221")
        guards_state["fields"][0]["controller"] = 0
        guards_state["phase"], guards_state["actor"] = "main", 0
        guards_state["players"][0]["power"] = ["order"] * 5
        hide = next(action for action in guards_rules.legal_actions(guards_state)
                    if action.kind == "hide_card"
                    and __import__("json").loads(action.arguments)["card"] == guards_card)
        guards_rules.apply(guards_state, hide, random.Random(202))
        guards_state["turn"] = 1
        play_hidden = next(action for action in guards_rules.legal_actions(guards_state)
                           if action.kind == "play_hidden")
        guards_rules.apply(guards_state, play_hidden, random.Random(203))
        guards_rules.apply(guards_state, Action.make("pass"), random.Random(204))
        guards_rules.apply(guards_state, Action.make("pass"), random.Random(205))
        optional = guards_state["optional"][0]
        self.assertEqual(optional["effect"], "guards_ready")
        guards_rules.apply(
            guards_state,
            Action.make("optional_effect", optional=optional["id"], accept=True),
            random.Random(206),
        )
        self.assertEqual(sum(unit["code"] == "SFD-T04" for unit in guards_state["units"]), 1)
        self.assertFalse(guards_state["units"][0]["exhausted"])
        self.assertEqual(guards_state["players"][0]["power"], ["order"] * 3)

        with open("examples/spiritforged-cluster.json") as stream:
            example = __import__("json").load(stream)
        arise_rules = SpiritforgedRules([example, example])
        arise_state = arise_rules.initial_state(random.Random(207))
        arise_card = "p0:arise"
        arise_state["cards"][arise_card] = {"code": "SFD-198-221", "owner": 0}
        arise_state["players"][0]["hand"].append(arise_card)
        arise_state["players"][0]["energy"] = 20
        arise_state["players"][0]["power"] = ["calm"] * 20
        for index in range(3):
            arise_state["players"][0]["gear"].append({
                "id": f"gear:arise:{index}", "card": None, "code": "OGN-040",
                "owner": 0, "card_owner": 0, "location": "base:0",
                "exhausted": False, "temporary": False,
            })
        arise_state["phase"], arise_state["actor"] = "main", 0
        play = next(action for action in arise_rules.legal_actions(arise_state)
                    if action.kind == "play_spell"
                    and __import__("json").loads(action.arguments)["card"] == arise_card)
        arise_rules.apply(arise_state, play, random.Random(208))
        arise_rules.apply(arise_state, Action.make("pass"), random.Random(209))
        arise_rules.apply(arise_state, Action.make("pass"), random.Random(210))
        self.assertEqual(arise_state["decision"]["max"], 2)
        token_ids = [unit["id"] for unit in arise_state["units"]]
        for token_id in token_ids[:2]:
            arise_rules.apply(arise_state, Action.make("choose_target", target=token_id), random.Random(211))
        arise_rules.apply(arise_state, Action.make("confirm_targets"), random.Random(212))
        self.assertEqual(sum(unit["code"] == "SFD-T04" for unit in arise_state["units"]), 3)
        self.assertEqual(sum(not unit["exhausted"] for unit in arise_state["units"]), 2)

        cask_state = arise_rules.initial_state(random.Random(213))
        spell = "p0:cask-spell"
        cask_state["cards"][spell] = {"code": "OGN-083", "owner": 0}
        cask_state["players"][0]["hand"].append(spell)
        cask_state["players"][0]["gear"].append({
            "id": "gear:cask", "card": None, "code": "SFD-063-221", "owner": 0,
            "card_owner": 0, "location": "base:0", "exhausted": False, "temporary": False,
        })
        cask_state["phase"], cask_state["actor"] = "main", 0
        cask_state["turn_player"] = 1
        cask_state["players"][0]["energy"] = 20
        cask_state["players"][0]["power"] = ["mind"] * 20
        play = next(action for action in arise_rules.legal_actions(cask_state)
                    if action.kind == "play_spell"
                    and __import__("json").loads(action.arguments)["card"] == spell)
        arise_rules.apply(cask_state, play, random.Random(214))
        for seed in (215, 216, 217, 218):
            if cask_state["phase"] != "chain":
                break
            arise_rules.apply(cask_state, Action.make("pass"), random.Random(seed))
        optional = cask_state["optional"][0]
        self.assertEqual(optional["effect"], "chemtech_gold")
        arise_rules.apply(cask_state,
                          Action.make("optional_effect", optional=optional["id"], accept=True),
                          random.Random(219))
        self.assertTrue(cask_state["players"][0]["gear"][0]["exhausted"])
        self.assertEqual(sum(gear["code"] == "SFD-T03" for gear in cask_state["players"][0]["gear"]), 1)

    def test_batch_choice_triggers_and_zaun_punk_additional_gear(self):
        with open("examples/spiritforged-cluster.json") as stream:
            example = __import__("json").load(stream)
        rules = SpiritforgedRules([example, example])

        jae_state = rules.initial_state(random.Random(220))
        spell = "p0:jae-spell"
        jae_state["cards"][spell] = {"code": "SFD-034-221", "owner": 0}
        jae_state["players"][0]["hand"].append(spell)
        jae = rules._new_unit(jae_state, "SFD-142-221", 1, 0, exhausted=False)
        jae_state["phase"], jae_state["actor"] = "main", 0
        jae_state["players"][0]["energy"] = 20
        jae_state["players"][0]["power"] = ["fury"] * 20
        play = next(action for action in rules.legal_actions(jae_state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == spell)
        rules.apply(jae_state, play, random.Random(221))
        rules.apply(jae_state, Action.make("choose_target", target=jae["id"]), random.Random(222))
        self.assertEqual(jae_state["chain"][-1]["effect"], "draw_one")
        self.assertEqual(jae_state["chain"][-1]["owner"], 1)

        wheel_state = rules.initial_state(random.Random(223))
        wheel_spell = "p0:wheel-spell"
        wheel_state["cards"][wheel_spell] = {"code": "SFD-034-221", "owner": 0}
        wheel_state["players"][0]["hand"].append(wheel_spell)
        friendly = rules._new_unit(wheel_state, "OGN-001", 0, 0, exhausted=False)
        wheel_state["players"][0]["gear"].append({
            "id": "gear:wheel", "card": None, "code": "SFD-144-221", "owner": 0,
            "card_owner": 0, "location": "base:0", "exhausted": False, "temporary": False,
        })
        wheel_state["phase"], wheel_state["actor"] = "main", 0
        wheel_state["players"][0]["energy"] = 20
        wheel_state["players"][0]["power"] = ["fury"] * 20
        play = next(action for action in rules.legal_actions(wheel_state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == wheel_spell)
        rules.apply(wheel_state, play, random.Random(224))
        rules.apply(wheel_state, Action.make("choose_target", target=friendly["id"]), random.Random(225))
        for seed in (226, 227, 228, 229):
            if wheel_state["phase"] != "chain":
                break
            rules.apply(wheel_state, Action.make("pass"), random.Random(seed))
        optional = wheel_state["optional"][0]
        self.assertEqual(optional["effect"], "spirit_wheel_draw")
        rules.apply(wheel_state,
                    Action.make("optional_effect", optional=optional["id"], accept=True),
                    random.Random(230))
        self.assertTrue(wheel_state["players"][0]["gear"][0]["exhausted"])

        punk_deck = legal_deck("SFD-160-221", "OGN-253", "OGN-243")
        punk_rules = SpiritforgedRules([punk_deck, punk_deck])
        punk_state = punk_rules.initial_state(random.Random(231))
        punk_card = move_code_to_hand(punk_state, 0, "SFD-160-221")
        punk_state["players"][0]["gear"].extend([
            {"id": "gear:punk:cost", "card": None, "code": "OGN-040", "owner": 0,
             "card_owner": 0, "location": "base:0", "exhausted": False, "temporary": False},
            {"id": "gear:punk:target", "card": None, "code": "OGN-081", "owner": 0,
             "card_owner": 0, "location": "base:0", "exhausted": False, "temporary": False},
        ])
        punk_state["phase"], punk_state["actor"] = "main", 0
        punk_state["players"][0]["energy"] = 20
        punk_state["players"][0]["power"] = ["order"] * 20
        play = next(action for action in punk_rules.legal_actions(punk_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == punk_card
                    and __import__("json").loads(action.arguments)["additional_cost"])
        punk_rules.apply(punk_state, play, random.Random(232))
        self.assertNotIn("gear:punk:cost", [gear["id"] for gear in punk_state["players"][0]["gear"]])
        self.assertEqual(punk_state["decision"]["targets"], ["gear:punk:target"])
        punk_rules.apply(punk_state, Action.make("choose_target", target="gear:punk:target"), random.Random(235))
        punk_rules.apply(punk_state, Action.make("pass"), random.Random(236))
        punk_rules.apply(punk_state, Action.make("pass"), random.Random(237))
        self.assertEqual(punk_state["players"][0]["gear"], [])

    def test_batch_ganking_deathknell_and_mech_aura_hooks(self):
        gank_deck = legal_deck("SFD-007-221", "OGN-247", "OGN-039")
        gank_rules = SpiritforgedRules([gank_deck, gank_deck])
        gank_state = gank_rules.initial_state(random.Random(142))
        gank_card = move_code_to_hand(gank_state, 0, "SFD-007-221")
        target = gank_rules._new_unit(gank_state, "OGN-001", 1, 0, exhausted=False)
        gank_state["phase"], gank_state["actor"] = "main", 0
        gank_state["players"][0]["energy"] = 10
        gank_state["players"][0]["power"] = ["fury"] * 10
        play = next(action for action in gank_rules.legal_actions(gank_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == gank_card)
        gank_rules.apply(gank_state, play, random.Random(143))
        gank_rules.apply(gank_state, Action.make("choose_target", target=target["id"]), random.Random(144))
        gank_rules.apply(gank_state, Action.make("pass"), random.Random(145))
        gank_rules.apply(gank_state, Action.make("pass"), random.Random(146))
        self.assertTrue(target["temporary_ganking"])

        death_deck = legal_deck("SFD-021-221", "OGN-247", "OGN-039")
        death_rules = SpiritforgedRules([death_deck, death_deck])
        death_state = death_rules.initial_state(random.Random(147))
        doomed = death_rules._new_unit(death_state, "SFD-021-221", 0, 0, exhausted=False)
        doomed["damage"] = death_rules.might(death_state, doomed)
        death_rules._cleanup(death_state, random.Random(148))
        self.assertEqual(sum(unit["code"] == "SFD-T05" for unit in death_state["units"]), 2)

        aura_deck = legal_deck("SFD-089-221", "OGN-255", "OGN-119")
        aura_rules = SpiritforgedRules([aura_deck, aura_deck])
        aura_state = aura_rules.initial_state(random.Random(149))
        aura = aura_rules._new_unit(aura_state, "SFD-089-221", 0, 0, exhausted=False)
        mech = aura_rules._new_unit(aura_state, "OGN-088", 0, 0, exhausted=False)
        self.assertEqual(aura_rules.might(aura_state, mech), 9)
        aura_state["fields"][0]["controller"] = 0
        aura_rules._score(aura_state, 0, 0, "hold", random.Random(150))
        self.assertEqual(sum(unit["code"] == "SFD-T05" for unit in aura_state["units"]), 1)

    def test_batch_cost_and_placement_rules_and_entry_kill(self):
        ram_deck = legal_deck("SFD-012-221", "OGN-247", "OGN-039")
        ram_rules = SpiritforgedRules([ram_deck, ram_deck])
        ram_state = ram_rules.initial_state(random.Random(151))
        ram_card = move_code_to_hand(ram_state, 0, "SFD-012-221")
        ram_state["players"][0]["finalized_played"] = 3
        ram_state["players"][0]["played"] = 3
        ram_state["phase"], ram_state["actor"] = "main", 0
        ram_state["players"][0]["energy"] = 2
        ram_state["players"][0]["power"] = ["fury"] * 5
        ram_action = next(action for action in ram_rules.legal_actions(ram_state)
                          if action.kind == "play_unit"
                          and __import__("json").loads(action.arguments)["card"] == ram_card)
        self.assertEqual(__import__("json").loads(ram_action.arguments)["location"], "base:0")

        grim_deck = legal_deck("SFD-015-221", "OGN-247", "OGN-039")
        grim_rules = SpiritforgedRules([grim_deck, grim_deck])
        grim_state = grim_rules.initial_state(random.Random(152))
        grim_card = move_code_to_hand(grim_state, 0, "SFD-015-221")
        grim_state["scored"][0] = [0]
        grim_state["phase"], grim_state["actor"] = "main", 0
        grim_state["players"][0]["energy"] = 10
        grim_state["players"][0]["power"] = ["fury"] * 10
        grim_locations = {__import__("json").loads(action.arguments)["location"]
                          for action in grim_rules.legal_actions(grim_state)
                          if action.kind == "play_unit"
                          and __import__("json").loads(action.arguments)["card"] == grim_card}
        self.assertEqual(grim_locations, {0})

        vanguard_deck = legal_deck("SFD-093-221", "OGN-267", "OGN-162")
        vanguard_rules = SpiritforgedRules([vanguard_deck, vanguard_deck])
        vanguard_state = vanguard_rules.initial_state(random.Random(153))
        vanguard_card = move_code_to_hand(vanguard_state, 0, "SFD-093-221")
        vanguard_rules._new_unit(vanguard_state, "OGN-001", 1, 0, exhausted=False)
        vanguard_state["phase"], vanguard_state["actor"] = "main", 0
        vanguard_state["players"][0]["energy"] = 10
        vanguard_state["players"][0]["power"] = ["body"] * 10
        vanguard_locations = {__import__("json").loads(action.arguments)["location"]
                              for action in vanguard_rules.legal_actions(vanguard_state)
                              if action.kind == "play_unit"
                              and __import__("json").loads(action.arguments)["card"] == vanguard_card}
        self.assertIn(0, vanguard_locations)

        shifter_deck = legal_deck("SFD-158-221", "OGN-253", "OGN-243")
        shifter_rules = SpiritforgedRules([shifter_deck, shifter_deck])
        shifter_state = shifter_rules.initial_state(random.Random(154))
        shifter_card = move_code_to_hand(shifter_state, 0, "SFD-158-221")
        victim = shifter_rules._new_unit(shifter_state, "OGN-003", 1, 0, exhausted=False)
        shifter_state["phase"], shifter_state["actor"] = "main", 0
        shifter_state["players"][0]["energy"] = 10
        shifter_state["players"][0]["power"] = ["order"] * 10
        play = next(action for action in shifter_rules.legal_actions(shifter_state)
                    if action.kind == "play_unit"
                    and __import__("json").loads(action.arguments)["card"] == shifter_card)
        shifter_rules.apply(shifter_state, play, random.Random(155))
        shifter_rules.apply(shifter_state, Action.make("choose_target", target=victim["id"]), random.Random(156))
        shifter_rules.apply(shifter_state, Action.make("pass"), random.Random(157))
        shifter_rules.apply(shifter_state, Action.make("pass"), random.Random(158))
        self.assertNotIn(victim, shifter_state["units"])

    def test_batch_global_movement_scoring_and_accelerate_hooks(self):
        lock_deck = legal_deck("SFD-014-221", "OGN-247", "OGN-039")
        lock_rules = SpiritforgedRules([lock_deck, lock_deck])
        lock_state = lock_rules.initial_state(random.Random(159))
        reckoner = lock_rules._new_unit(lock_state, "SFD-014-221", 0, "base:0", exhausted=False)
        mover = lock_rules._new_unit(lock_state, "OGN-001", 0, 0, exhausted=False)
        lock_state["phase"], lock_state["actor"] = "main", 0
        self.assertEqual(lock_rules._movable(lock_state, "base:0"), [])
        with self.assertRaisesRegex(ValueError, "cannot move to base"):
            lock_rules._resolve_move(lock_state, [mover], "base:0", 0, random.Random(160))
        self.assertIn(reckoner, lock_state["units"])

        score_deck = legal_deck("SFD-060-221", "OGN-255", "OGN-119")
        score_rules = SpiritforgedRules([score_deck, score_deck])
        score_state = score_rules.initial_state(random.Random(161))
        score_rules._new_unit(score_state, "SFD-060-221", 1, 0, exhausted=False)
        score_state["fields"][0]["controller"] = 0
        before_points = list(score_state["points"])
        score_rules._score(score_state, 0, 0, "hold", random.Random(162))
        self.assertEqual(score_state["points"], before_points)

        warmonger_deck = legal_deck("SFD-131-221", "OGN-267", "OGN-193")
        warmonger_rules = SpiritforgedRules([warmonger_deck, warmonger_deck])
        warmonger_state = warmonger_rules.initial_state(random.Random(163))
        warmonger = warmonger_rules._new_unit(warmonger_state, "SFD-131-221", 0, 0, exhausted=False)
        warmonger_rules._new_unit(warmonger_state, "OGN-003", 1, 0, exhausted=False)
        warmonger_state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        self.assertTrue(warmonger_rules._is_accelerate_code("SFD-131-221"))
        self.assertEqual(warmonger_rules.might(warmonger_state, warmonger), 5)

    def test_batch_lucian_attack_uses_combat_trigger_target_window(self):
        deck = legal_deck("SFD-028-221", "OGN-247", "OGN-039")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(164))
        lucian = rules._new_unit(state, "SFD-028-221", 0, 0, exhausted=False)
        target = rules._new_unit(state, "OGN-003", 1, 0, exhausted=False)
        state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        before = target["damage"]
        rules._effect_lucian_attack(
            state, {"effect": "lucian_attack", "owner": 0,
                    "source": lucian["id"], "target": target["id"], "field": 0},
            random.Random(165))
        self.assertEqual(target["damage"], before + 1)

    def test_batch_gear_entries_activated_targets_and_token_destinations(self):
        poro_deck = legal_deck("SFD-046-221", "OGN-255", "OGN-119")
        poro_rules = SpiritforgedRules([poro_deck, poro_deck])
        poro_state = poro_rules.initial_state(random.Random(166))
        poro_card = move_code_to_hand(poro_state, 0, "SFD-046-221")
        poro_state["phase"], poro_state["actor"] = "main", 0
        poro_state["players"][0]["energy"] = 5
        poro_state["players"][0]["power"] = ["calm"] * 5
        hand_before = len(poro_state["players"][0]["hand"])
        play = next(action for action in poro_rules.legal_actions(poro_state)
                    if action.kind == "play_gear"
                    and __import__("json").loads(action.arguments)["card"] == poro_card)
        poro_rules.apply(poro_state, play, random.Random(167))
        poro_rules.apply(poro_state, Action.make("pass"), random.Random(168))
        poro_rules.apply(poro_state, Action.make("pass"), random.Random(169))
        self.assertEqual(len(poro_state["players"][0]["hand"]), hand_before)
        gear = next(g for g in poro_state["players"][0]["gear"] if g["id"] == poro_card)
        activate = next(action for action in poro_rules.legal_actions(poro_state)
                        if action.kind == "gear_activate"
                        and __import__("json").loads(action.arguments)["gear"] == gear["id"])
        poro_rules.apply(poro_state, activate, random.Random(170))
        self.assertNotIn(gear, poro_state["players"][0]["gear"])
        self.assertEqual(len(poro_state["players"][0]["hand"]), hand_before + 1)

        heart_deck = legal_deck("SFD-052-221", "OGN-255", "OGN-119")
        heart_rules = SpiritforgedRules([heart_deck, heart_deck])
        heart_state = heart_rules.initial_state(random.Random(171))
        heart_card = move_code_to_hand(heart_state, 0, "SFD-052-221")
        target = heart_rules._new_unit(heart_state, "OGN-001", 1, "base:1", exhausted=False)
        heart_state["phase"], heart_state["actor"] = "main", 0
        heart_state["players"][0]["energy"] = 5
        heart_state["players"][0]["power"] = ["calm"] * 5
        play = next(action for action in heart_rules.legal_actions(heart_state)
                    if action.kind == "play_gear"
                    and __import__("json").loads(action.arguments)["card"] == heart_card)
        heart_rules.apply(heart_state, play, random.Random(172))
        heart = next(g for g in heart_state["players"][0]["gear"] if g["id"] == heart_card)
        targeted = next(action for action in heart_rules.legal_actions(heart_state)
                        if action.kind == "gear_targeted"
                        and __import__("json").loads(action.arguments)["gear"] == heart["id"])
        heart_rules.apply(heart_state, targeted, random.Random(173))
        heart_rules.apply(heart_state, Action.make("choose_target", target=target["id"]), random.Random(174))
        self.assertEqual(target["temporary"], 3)
        self.assertTrue(heart["exhausted"])

        armory_deck = legal_deck("SFD-168-221", "OGN-253", "OGN-243")
        armory_rules = SpiritforgedRules([armory_deck, armory_deck])
        armory_state = armory_rules.initial_state(random.Random(175))
        armory_card = move_code_to_hand(armory_state, 0, "SFD-168-221")
        armory_state["phase"], armory_state["actor"] = "main", 0
        armory_state["players"][0]["energy"] = 10
        armory_state["players"][0]["power"] = ["order"] * 10
        play = next(action for action in armory_rules.legal_actions(armory_state)
                    if action.kind == "play_gear"
                    and __import__("json").loads(action.arguments)["card"] == armory_card)
        armory_rules.apply(armory_state, play, random.Random(176))
        armory = next(g for g in armory_state["players"][0]["gear"] if g["id"] == armory_card)
        activate = next(action for action in armory_rules.legal_actions(armory_state)
                        if action.kind == "gear_tokens"
                        and __import__("json").loads(action.arguments)["gear"] == armory["id"])
        armory_rules.apply(armory_state, activate, random.Random(177))
        for _ in range(3):
            armory_rules.apply(armory_state, Action.make("choose_field", field="base:0"), random.Random(178))
        self.assertTrue(armory["exhausted"])
        self.assertEqual(sum(unit["code"] == "OGN-273" for unit in armory_state["units"]), 3)

    def test_batch_registry_combat_conquer_rally_and_ordered_target_spell(self):
        fiora_deck = legal_deck("SFD-110-221", "OGN-267", "OGN-162")
        fiora_rules = SpiritforgedRules([fiora_deck, fiora_deck])
        fiora_state = fiora_rules.initial_state(random.Random(179))
        fiora = fiora_rules._new_unit(fiora_state, "SFD-110-221", 0, 0, exhausted=False)
        fiora_rules._new_unit(fiora_state, "OGN-001", 1, 0, exhausted=False)
        fiora_state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        self.assertEqual(fiora_rules.might(fiora_state, fiora), 6)

        yone_deck = legal_deck("SFD-116-221", "OGN-267", "OGN-162")
        yone_rules = SpiritforgedRules([yone_deck, yone_deck])
        yone_state = yone_rules.initial_state(random.Random(180))
        yone = yone_rules._new_unit(yone_state, "SFD-116-221", 0, 0, exhausted=False)
        enemy_base = yone_rules._new_unit(yone_state, "OGN-001", 1, "base:1", exhausted=False)
        yone_state["fields"][0]["controller"] = None
        yone_rules._score(yone_state, 0, 0, "conquer", random.Random(181), uncontrolled=True)
        optional = next(item for item in yone_state["optional"] if item["effect"] == "yone_conquer_damage")
        yone_rules.apply(yone_state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(182))
        yone_rules.apply(yone_state, Action.make("choose_target", target=enemy_base["id"]), random.Random(183))
        self.assertEqual(enemy_base["damage"], yone_rules.might(yone_state, yone))

        rally_deck = legal_deck("SFD-166-221", "OGN-253", "OGN-243")
        rally_rules = SpiritforgedRules([rally_deck, rally_deck])
        rally_state = rally_rules.initial_state(random.Random(184))
        rally_card = move_code_to_hand(rally_state, 0, "SFD-166-221")
        rally_state["phase"], rally_state["actor"] = "main", 0
        rally_state["players"][0]["energy"] = 5
        rally_state["players"][0]["power"] = ["order"] * 5
        play = next(action for action in rally_rules.legal_actions(rally_state)
                    if action.kind == "play_spell"
                    and __import__("json").loads(action.arguments)["card"] == rally_card)
        rally_rules.apply(rally_state, play, random.Random(185))
        rally_rules.apply(rally_state, Action.make("pass"), random.Random(186))
        rally_rules.apply(rally_state, Action.make("pass"), random.Random(187))
        self.assertEqual(rally_state["rally_effects"][0]["turn"], rally_state["turn"])

        grip_deck = legal_deck("SFD-163-221", "OGN-253", "OGN-243")
        grip_rules = SpiritforgedRules([grip_deck, grip_deck])
        grip_state = grip_rules.initial_state(random.Random(188))
        grip_card = move_code_to_hand(grip_state, 0, "SFD-163-221")
        killed = grip_rules._new_unit(grip_state, "OGN-001", 0, "base:0", exhausted=False)
        recipient = grip_rules._new_unit(grip_state, "OGN-001", 0, "base:0", exhausted=False)
        grip_state["phase"], grip_state["actor"] = "main", 0
        grip_state["players"][0]["energy"] = 5
        grip_state["players"][0]["power"] = ["order"] * 5
        play = next(action for action in grip_rules.legal_actions(grip_state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == grip_card)
        grip_rules.apply(grip_state, play, random.Random(189))
        grip_rules.apply(grip_state, Action.make("choose_target", target=killed["id"]), random.Random(190))
        grip_rules.apply(grip_state, Action.make("choose_target", target=recipient["id"]), random.Random(191))
        grip_rules.apply(grip_state, Action.make("confirm_targets"), random.Random(192))
        grip_rules.apply(grip_state, Action.make("pass"), random.Random(193))
        grip_rules.apply(grip_state, Action.make("pass"), random.Random(194))
        self.assertNotIn(killed, grip_state["units"])
        self.assertEqual(recipient["temporary"], 5)

    def test_batch_spell_target_windows_and_damage_hooks(self):
        cases = (
            ("SFD-003-221", "OGN-247", "OGN-039", "friendly", "assault"),
            ("SFD-017-221", "OGN-247", "OGN-039", "enemy", "damage"),
            ("SFD-070-221", "OGN-247", "OGN-039", "enemy", "gold"),
        )
        for code, legend, champion, side, expected in cases:
            deck = legal_deck(code, legend, champion)
            rules = SpiritforgedRules([deck, deck])
            state = rules.initial_state(random.Random(200))
            card = move_code_to_hand(state, 0, code)
            state["phase"], state["actor"] = "main", 0
            state["players"][0]["energy"] = 20
            state["players"][0]["power"] = ["body"] * 20
            owner = 0 if side == "friendly" else 1
            target = rules._new_unit(state, "OGN-001", owner, 0, exhausted=False)
            state["fields"][0]["controller"] = owner
            play = next(action for action in rules.legal_actions(state)
                        if action.kind == "play_spell_targeted"
                        and __import__("json").loads(action.arguments)["card"] == card)
            args = __import__("json").loads(play.arguments)
            self.assertIn(target["id"], args["target_candidates"])
            rules.apply(state, play, random.Random(201))
            rules.apply(state, Action.make("choose_target", target=target["id"]), random.Random(202))
            rules.apply(state, Action.make("pass"), random.Random(203))
            rules.apply(state, Action.make("pass"), random.Random(204))
            if expected == "assault":
                self.assertEqual(target["assault"], 2)
            elif expected == "damage":
                self.assertEqual(target["damage"], 2)
            else:
                self.assertEqual(sum(g["code"] == "SFD-T03"
                                     for g in state["players"][0]["gear"]), 1)

        stun_deck = legal_deck("SFD-040-221", "OGN-255", "OGN-066")
        stun_rules = SpiritforgedRules([stun_deck, stun_deck])
        stun_state = stun_rules.initial_state(random.Random(205))
        stun_card = move_code_to_hand(stun_state, 0, "SFD-040-221")
        attacker = stun_rules._new_unit(stun_state, "OGN-001", 1, 0, exhausted=False)
        stun_state["battle"] = {"field": 0, "attacker": 1, "combat": True}
        stun_state["phase"], stun_state["actor"] = "showdown", 0
        stun_state["players"][0]["energy"] = 5
        stun_state["players"][0]["power"] = ["calm"] * 5
        play = next(action for action in stun_rules.legal_actions(stun_state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == stun_card)
        stun_rules.apply(stun_state, play, random.Random(206))
        stun_rules.apply(stun_state, Action.make("choose_target", target=attacker["id"]), random.Random(207))
        stun_rules.apply(stun_state, Action.make("pass"), random.Random(208))
        stun_rules.apply(stun_state, Action.make("pass"), random.Random(209))
        self.assertTrue(attacker["stunned"])

        bond_deck = legal_deck("SFD-151-221", "OGN-253", "OGN-243")
        bond_rules = SpiritforgedRules([bond_deck, bond_deck])
        bond_state = bond_rules.initial_state(random.Random(210))
        bond_card = move_code_to_hand(bond_state, 0, "SFD-151-221")
        first = bond_rules._new_unit(bond_state, "OGN-001", 0, "base:0", exhausted=False)
        second = bond_rules._new_unit(bond_state, "OGN-001", 0, 0, exhausted=False)
        bond_state["phase"], bond_state["actor"] = "main", 0
        bond_state["players"][0]["energy"] = 5
        bond_state["players"][0]["power"] = ["order"] * 5
        play = next(action for action in bond_rules.legal_actions(bond_state)
                    if action.kind == "play_spell_targeted"
                    and __import__("json").loads(action.arguments)["card"] == bond_card)
        bond_rules.apply(bond_state, play, random.Random(211))
        bond_rules.apply(bond_state, Action.make("choose_target", target=first["id"]), random.Random(212))
        bond_rules.apply(bond_state, Action.make("choose_target", target=second["id"]), random.Random(213))
        bond_rules.apply(bond_state, Action.make("confirm_targets"), random.Random(214))
        bond_rules.apply(bond_state, Action.make("pass"), random.Random(215))
        bond_rules.apply(bond_state, Action.make("pass"), random.Random(216))
        self.assertEqual(first["temporary"], 1)
        self.assertEqual(second["temporary"], 1)

    def test_batch_move_reveal_yordle_and_temporary_deflect(self):
        smith_deck = legal_deck("SFD-041-221", "OGN-255", "OGN-066")
        smith_rules = SpiritforgedRules([smith_deck, smith_deck])
        smith_state = smith_rules.initial_state(random.Random(210))
        smith_card = move_code_to_hand(smith_state, 0, "SFD-041-221")
        smith = smith_rules._new_unit(smith_state, "SFD-041-221", 0, "base:0",
                                      card=smith_card, exhausted=False)
        smith_state["phase"], smith_state["actor"] = "main", 0
        smith_state["fields"][0]["controller"] = 0
        top = smith_state["players"][0]["main"][0]
        smith_state["cards"][top]["code"] = "SFD-046-221"
        smith_rules._resolve_move(smith_state, [smith], 0, 0, random.Random(211))
        smith_rules.apply(smith_state, Action.make("pass"), random.Random(212))
        smith_rules.apply(smith_state, Action.make("pass"), random.Random(213))
        self.assertEqual(smith_state["phase"], "reveal")
        smith_rules.apply(smith_state, Action.make("end_reveal"), random.Random(214))
        self.assertIn(top, smith_state["players"][0]["hand"])

        enforcer_deck = legal_deck("SFD-123-221", "OGN-267", "OGN-162")
        enforcer_rules = SpiritforgedRules([enforcer_deck, enforcer_deck])
        enforcer_state = enforcer_rules.initial_state(random.Random(215))
        enforcer = enforcer_rules._new_unit(enforcer_state, "SFD-123-221", 0, "base:0",
                                            exhausted=False)
        enforcer_state["players"][0]["hand"] = enforcer_state["players"][0]["hand"][:1]
        enforcer_state["phase"], enforcer_state["actor"] = "main", 0
        enforcer_state["fields"][0]["controller"] = 0
        enforcer_rules._resolve_move(enforcer_state, [enforcer], 0, 0, random.Random(216))
        enforcer_rules.apply(enforcer_state, Action.make("pass"), random.Random(217))
        enforcer_rules.apply(enforcer_state, Action.make("pass"), random.Random(218))
        self.assertEqual(enforcer_state["phase"], "decision")
        self.assertEqual(enforcer_state["decision"]["kind"], "discard")

        yordle_deck = legal_deck("SFD-100-221", "OGN-257", "OGN-151")
        yordle_rules = SpiritforgedRules([yordle_deck, yordle_deck])
        yordle_state = yordle_rules.initial_state(random.Random(219))
        yordle_rules._new_unit(yordle_state, "SFD-100-221", 0, "base:0", exhausted=False)
        played = next(uid for uid in yordle_state["players"][0]["main"]
                      if yordle_rules.cards[yordle_state["cards"][uid]["code"]].get("power_cost", 0) >= 2)
        yordle_state["players"][0]["main"].remove(played)
        yordle_state["players"][0]["hand"].append(played)
        before = len(yordle_state["players"][0]["hand"])
        yordle_rules._mark_play_finalized(yordle_state, 0, played, rng=random.Random(220))
        self.assertEqual(len(yordle_state["players"][0]["hand"]), before + 1)

        shield_deck = legal_deck("SFD-104-221", "OGN-257", "OGN-151")
        shield_rules = SpiritforgedRules([shield_deck, shield_deck])
        shield_state = shield_rules.initial_state(random.Random(221))
        shield_state["players"][0]["legend"] = "SFD-181-221"
        mech = shield_rules._new_unit(shield_state, "SFD-T05", 0, 0, exhausted=False)
        shield_state["battle"] = {"field": 0, "attacker": 1, "combat": True}
        self.assertEqual(shield_rules.might(shield_state, mech), 4)
        shield = move_code_to_hand(shield_state, 0, "SFD-104-221")
        shield_state["phase"], shield_state["actor"] = "main", 0
        shield_state["players"][0]["energy"] = 5
        shield_state["players"][0]["power"] = ["body"] * 5
        play = next(action for action in shield_rules.legal_actions(shield_state)
                    if action.kind == "play_gear"
                    and __import__("json").loads(action.arguments)["card"] == shield)
        shield_rules.apply(shield_state, play, random.Random(222))
        self.assertTrue(shield_rules._deflect(shield_state, mech))

    def test_batch_aliases_use_shared_trigger_and_resource_paths(self):
        # Renata's alternate printing still uses the token-ready predicate.
        renata_deck = legal_deck("SFD-171A-221", "OGN-253", "OGN-243")
        renata_rules = SpiritforgedRules([renata_deck, renata_deck])
        renata_state = renata_rules.initial_state(random.Random(223))
        renata_rules._new_unit(renata_state, "SFD-171A-221", 0, "base:0", exhausted=False)
        token = renata_rules._new_unit(renata_state, "OGN-273", 0, "base:0", exhausted=True)
        self.assertFalse(token["exhausted"])

        # Ahri's alternate printing opens the same pre-chain target window.
        ahri_deck = legal_deck("SFD-227-221", "OGN-247", "OGN-039")
        ahri_rules = SpiritforgedRules([ahri_deck, ahri_deck])
        ahri_state = ahri_rules.initial_state(random.Random(224))
        ahri = ahri_rules._new_unit(ahri_state, "SFD-227-221", 0, 0, exhausted=False)
        enemy = ahri_rules._new_unit(ahri_state, "OGN-001", 1, 0, exhausted=False)
        ahri_state.update(phase="showdown", actor=0, focus=0, passes=0,
                          battle={"field": 0, "attacker": 0, "combat": True})
        ahri_rules._close_showdown(ahri_state, random.Random(225))
        self.assertEqual(ahri_state["decision"]["targets"], [enemy["id"]])
        ahri_rules.apply(ahri_state, Action.make("choose_target", target=enemy["id"]), random.Random(226))
        ahri_rules.apply(ahri_state, Action.make("pass"), random.Random(227))
        ahri_rules.apply(ahri_state, Action.make("pass"), random.Random(228))
        self.assertEqual(enemy["temporary"], -2)

        # Darius's alternate printing grants a local aura and Legion entry check.
        darius_deck = legal_deck("SFD-236-221", "OGN-253", "OGN-027")
        darius_rules = SpiritforgedRules([darius_deck, darius_deck])
        darius_state = darius_rules.initial_state(random.Random(229))
        darius = darius_rules._new_unit(darius_state, "SFD-236-221", 0, 0, exhausted=False)
        ally = darius_rules._new_unit(darius_state, "OGN-001", 0, 0, exhausted=False)
        darius_state["players"][0]["finalized_played"] = 1
        self.assertTrue(darius_rules._entry_ready(darius_state, darius["code"], 0))
        self.assertEqual(darius_rules.might(darius_state, ally), 6)

        # Karma's alternate printing is emitted for every ordinary recycle event.
        karma_deck = legal_deck("SFD-237-221", "OGN-261", "OGN-238")
        karma_rules = SpiritforgedRules([karma_deck, karma_deck])
        karma_state = karma_rules.initial_state(random.Random(230))
        karma_rules._new_unit(karma_state, "SFD-237-221", 0, "base:0", exhausted=False)
        karma_rules._trigger_recycle_event(karma_state, 0)
        self.assertEqual(karma_state["chain"][-1]["effect"], "karma_recycle")
        self.assertEqual(karma_state["decision"]["kind"], "target")

        # Glorious Executioner is a legend listener, so the legend path draws
        # once when its controller wins a combat.
        legend_deck = legal_deck("SFD-003-221", "OGN-253", "OGN-027")
        legend_rules = SpiritforgedRules([legend_deck, legend_deck])
        legend_state = legend_rules.initial_state(random.Random(231))
        legend_state["players"][0]["legend"] = "SFD-242-221"
        legend_rules._new_unit(legend_state, "OGN-001", 0, 0, exhausted=False)
        before = len(legend_state["players"][0]["hand"])
        legend_state["battle"] = {"field": 0, "attacker": 0, "combat": True}
        legend_rules._settle_battle(legend_state, random.Random(232))
        self.assertEqual(len(legend_state["players"][0]["hand"]), before + 1)

        # Yasuo's alternate move hook uses the common move counter.
        yasuo_deck = legal_deck("SFD-235-221", "OGN-267", "OGN-162")
        yasuo_rules = SpiritforgedRules([yasuo_deck, yasuo_deck])
        yasuo_state = yasuo_rules.initial_state(random.Random(233))
        yasuo = yasuo_rules._new_unit(yasuo_state, "SFD-235-221", 0, "base:0", exhausted=False)
        yasuo["move_count"] = 2
        yasuo_rules._resolve_move(yasuo_state, [yasuo], 0, 0, random.Random(234))
        self.assertEqual(yasuo_state["points"][0], 1)

    def test_batch_static_ready_cost_and_defend_hooks(self):
        # Needlessly Large Yordle uses a declarative Shield/Tank predicate and
        # the per-turn hold-point reduction in the ordinary unit payment path.
        yordle_deck = legal_deck("SFD-055-221", "OGN-261", "OGN-238")
        yordle_rules = SpiritforgedRules([yordle_deck, yordle_deck])
        yordle_state = yordle_rules.initial_state(random.Random(235))
        yordle_state["hold_points"][0] = 1
        yordle_card = move_code_to_hand(yordle_state, 0, "SFD-055-221")
        yordle_state.update(phase="main", actor=0)
        yordle_state["players"][0]["energy"] = 8
        yordle_state["players"][0]["power"] = ["calm"] * 5
        payment = next(action for action in yordle_rules.legal_actions(yordle_state)
                       if action.kind == "play_unit"
                       and __import__("json").loads(action.arguments)["card"] == yordle_card)
        self.assertEqual(__import__("json").loads(payment.arguments)["payment"], [0, 1, 2, 3, 4])
        yordle = yordle_rules._new_unit(yordle_state, "SFD-055-221", 0, 0, exhausted=False)
        yordle_state["battle"] = {"field": 0, "attacker": 1, "combat": True}
        self.assertEqual(yordle_rules.might(yordle_state, yordle), 10)
        self.assertTrue(yordle_rules._tank(yordle))

        # Vayne's entry condition and paid conquer recall share generic hooks.
        vayne_deck = legal_deck("SFD-223-221", "OGN-253", "OGN-027")
        vayne_rules = SpiritforgedRules([vayne_deck, vayne_deck])
        vayne_state = vayne_rules.initial_state(random.Random(236))
        vayne_card = move_code_to_hand(vayne_state, 0, "SFD-223-221")
        vayne_state["fields"][0]["controller"] = 1
        self.assertTrue(vayne_rules._entry_ready(vayne_state, "SFD-223-221", 0))
        vayne = vayne_rules._new_unit(vayne_state, "SFD-223-221", 0, 0,
                                      card=vayne_card, exhausted=False)
        vayne_state["players"][0]["energy"] = 1
        vayne_rules._score(vayne_state, 0, 0, "conquer", random.Random(237), uncontrolled=True)
        self.assertEqual(vayne_state["phase"], "optional")
        optional = vayne_state["optional"][0]
        vayne_rules.apply(vayne_state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(238))
        self.assertNotIn(vayne, vayne_state["units"])
        self.assertIn(vayne_card, vayne_state["players"][0]["hand"])

        # Sett's buff spend is exposed through the generic registered unit
        # ability action rather than a card-code-specific action.
        sett_deck = legal_deck("SFD-232-221", "OGN-269", "OGN-240")
        sett_rules = SpiritforgedRules([sett_deck, sett_deck])
        sett_state = sett_rules.initial_state(random.Random(239))
        sett = sett_rules._new_unit(sett_state, "SFD-232-221", 0, "base:0", exhausted=False)
        sett["buff"] = 1
        sett_state.update(phase="main", actor=0)
        action = next(action for action in sett_rules.legal_actions(sett_state)
                      if action.kind == "unit_registry_ability")
        sett_rules.apply(sett_state, action, random.Random(240))
        self.assertEqual(sett["buff"], 0)
        self.assertEqual(sett["temporary"], 4)
        self.assertTrue(sett["exhausted"])

        # Teemo's alternate printing uses the existing public reveal window.
        teemo_deck = legal_deck("SFD-230-221", "OGN-265", "OGN-246")
        teemo_rules = SpiritforgedRules([teemo_deck, teemo_deck])
        teemo_state = teemo_rules.initial_state(random.Random(241))
        teemo = teemo_rules._new_unit(teemo_state, "SFD-230-221", 1, 0, exhausted=False)
        target = teemo_rules._new_unit(teemo_state, "OGN-001", 0, 0, exhausted=False)
        top = teemo_state["players"][1]["main"][0]
        teemo_state["cards"][top]["code"] = "SFD-004-221"
        teemo_state.update(phase="showdown", actor=0, focus=0, passes=0,
                           battle={"field": 0, "attacker": 0, "combat": True})
        teemo_rules._close_showdown(teemo_state, random.Random(242))
        teemo_rules.apply(teemo_state, Action.make("choose_target", target=target["id"]), random.Random(243))
        teemo_rules.apply(teemo_state, Action.make("pass"), random.Random(244))
        teemo_rules.apply(teemo_state, Action.make("pass"), random.Random(245))
        self.assertEqual(teemo_state["phase"], "reveal")
        teemo_rules.apply(teemo_state, Action.make("end_reveal"), random.Random(246))
        teemo_rules.apply(teemo_state, Action.make("pass"), random.Random(247))
        teemo_rules.apply(teemo_state, Action.make("pass"), random.Random(248))
        self.assertEqual(target["damage"], 2)

    def test_batch_enemy_target_immunity_filters_shared_target_windows(self):
        deck = legal_deck("SFD-105-221", "OGN-267", "OGN-162")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(249))
        protected = rules._new_unit(state, "SFD-105-221", 0, 0, exhausted=False)
        ordinary = rules._new_unit(state, "OGN-001", 0, 0, exhausted=False)
        candidates = rules._registry_spell_target_candidates(state, 1, "any_unit")
        self.assertNotIn(protected["id"], candidates)
        self.assertIn(ordinary["id"], candidates)

    def test_batch_signature_ready_spell_reuses_ready_helper(self):
        deck = legal_deck("SFD-003-221", "OGN-253", "OGN-027")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(250))
        first = rules._new_unit(state, "OGN-001", 0, "base:0", exhausted=True)
        second = rules._new_unit(state, "SFD-055-221", 0, 0, exhausted=True)
        rules._effect_spell(state, {"code": "SFD-204-221", "owner": 0}, random.Random(251))
        self.assertFalse(first["exhausted"])
        self.assertFalse(second["exhausted"])

    def test_batch_unit_additional_return_gear_is_selected_in_play_action(self):
        deck = legal_deck("SFD-044-221", "OGN-261", "OGN-238")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(252))
        card = move_code_to_hand(state, 0, "SFD-044-221")
        gear = {"id": "gear:quartermaster", "card": None, "code": "OGN-040",
                "owner": 0, "card_owner": 0, "location": "base:0",
                "exhausted": False, "temporary": False}
        state["players"][0]["gear"].append(gear)
        state.update(phase="main", actor=0)
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["calm"] * 10
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "play_unit"
                      and __import__("json").loads(action.arguments)["card"] == card)
        args = __import__("json").loads(action.arguments)
        self.assertEqual(args["additional_gear"], gear["id"])
        rules.apply(state, action, random.Random(253))
        self.assertNotIn(gear, state["players"][0]["gear"])
        self.assertTrue(any(unit["code"] == "SFD-044-221" for unit in state["units"]))

    def test_batch_altar_memories_uses_draw_and_hand_destination_window(self):
        deck = legal_deck("SFD-003-221", "OGN-253", "OGN-027")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(254))
        altar = {"id": "gear:altar", "card": None, "code": "SFD-169-221",
                 "owner": 0, "card_owner": 0, "location": "base:0",
                 "exhausted": False, "temporary": False}
        state["players"][0]["gear"].append(altar)
        victim = rules._new_unit(state, "OGN-001", 0, 0, exhausted=False)
        victim["damage"] = rules.might(state, victim)
        before_main = list(state["players"][0]["main"])
        rules._cleanup(state, random.Random(255))
        self.assertEqual(state["phase"], "optional")
        self.assertEqual(state["optional"][0]["effect"], "altar_memories")
        optional = state["optional"][0]
        rules.apply(state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(256))
        self.assertEqual(state["decision"]["options"], ["top", "bottom"])
        rules.apply(state, Action.make("choose_option", option="top"), random.Random(257))
        chosen = state["decision"]["cards"][0]
        rules.apply(state, Action.make("choose_card", card=chosen), random.Random(258))
        self.assertTrue(altar["exhausted"])
        self.assertEqual(state["players"][0]["main"][0], chosen)
        self.assertNotIn(chosen, state["players"][0]["hand"])
        self.assertNotIn(victim, state["units"])
        self.assertEqual(len(state["players"][0]["main"]), len(before_main))

    def test_batch_card_sharp_opponent_choice_grants_the_matching_gold(self):
        deck = legal_deck("SFD-081-221", "OGN-247", "OGN-039")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(259))
        state.update(phase="main", actor=0)
        rules._effect_card_sharp(state, {"effect": "card_sharp", "owner": 0, "source": "u"}, random.Random(260))
        self.assertEqual([item["effect"] for item in state["optional"]],
                         ["card_sharp_self", "card_sharp_opponent"])
        first = state["optional"][0]
        rules.apply(state, Action.make("optional_effect", optional=first["id"], accept=True), random.Random(261))
        second = state["optional"][0]
        rules.apply(state, Action.make("optional_effect", optional=second["id"], accept=True), random.Random(262))
        self.assertEqual(sum(g["code"] == "SFD-T03" for g in state["players"][0]["gear"]), 2)
        self.assertEqual(sum(g["code"] == "SFD-T03" for g in state["players"][1]["gear"]), 1)

    def test_batch_spiritforged_battlefields_share_score_rules(self):
        deck = legal_deck("SFD-003-221", "OGN-253", "OGN-027")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(263))
        state["players"][0]["turns"] = 2
        state["fields"][0]["code"] = "SFD-209-221"
        state["fields"][0]["controller"] = 0
        points = list(state["points"])
        rules._score(state, 0, 0, "hold", random.Random(264))
        self.assertEqual(state["points"], points)

        state["players"][0]["turns"] = 3
        state["fields"][0]["code"] = "SFD-212-221"
        state["fields"][0]["controller"] = None
        state["scored"] = [[], []]
        before_trash = len(state["players"][0]["trash"])
        rules._score(state, 0, 0, "conquer", random.Random(265), uncontrolled=True)
        self.assertEqual(len(state["players"][0]["trash"]), before_trash + 2)

        state["fields"][0]["code"] = "SFD-219-221"
        state["fields"][0]["controller"] = 0
        state["scored"] = [[], []]
        state["players"][0]["rune_deck"] = [{"id": "r0", "code": "OGN-007", "exhausted": False}]
        state["players"][1]["rune_deck"] = [{"id": "r1", "code": "OGN-042", "exhausted": False}]
        rules._score(state, 0, 0, "hold", random.Random(266))
        self.assertEqual(len(state["players"][0]["runes"]), 1)
        self.assertEqual(len(state["players"][1]["runes"]), 1)

    def test_batch_rockfall_path_removes_unit_destination(self):
        deck = legal_deck("SFD-003-221", "OGN-253", "OGN-027")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(267))
        state["fields"][0]["code"] = "SFD-216-221"
        state["fields"][0]["controller"] = 0
        state.update(phase="main", actor=0)
        actions = rules.legal_actions(state)
        self.assertFalse(any(action.kind == "play_unit"
                             and __import__("json").loads(action.arguments).get("location") == 0
                             for action in actions))

    def test_batch_emperor_dais_requires_target_then_returns_unit_and_creates_soldier(self):
        deck = legal_deck("SFD-003-221", "OGN-253", "OGN-027")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(268))
        state["fields"][0]["code"] = "SFD-207-221"
        state["fields"][0]["controller"] = 0
        state["players"][0]["energy"] = 1
        unit = rules._new_unit(state, "OGN-001", 0, 0, exhausted=False, card=None)
        state["scored"] = [[], []]
        rules._score(state, 0, 0, "conquer", random.Random(269), uncontrolled=True)
        self.assertEqual(state["optional"][0]["effect"], "emperor_dais")
        optional = state["optional"][0]
        rules.apply(state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(270))
        rules.apply(state, Action.make("choose_target", target=unit["id"]), random.Random(271))
        self.assertNotIn(unit, state["units"])
        self.assertIn(unit.get("card"), state["players"][0]["hand"] if unit.get("card") else [None])
        self.assertTrue(any(token["code"] == "SFD-T04" and token["location"] == 0
                            for token in state["units"]))
        self.assertEqual(state["players"][0]["energy"], 0)

    def test_batch_ornns_forge_reduces_only_first_non_token_gear_each_turn(self):
        deck = legal_deck("SFD-003-221", "OGN-253", "OGN-027")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(272))
        state["fields"][0]["code"] = "SFD-213-221"
        state["fields"][0]["controller"] = 0
        gear_a = "p0:gear:a"
        gear_b = "p0:gear:b"
        state["cards"][gear_a] = {"code": "OGN-040", "owner": 0}
        state["cards"][gear_b] = {"code": "OGN-040", "owner": 0}
        state["players"][0]["hand"].extend([gear_a, gear_b])
        state.update(phase="main", actor=0)
        state["players"][0]["energy"] = 1
        state["players"][0]["power"] = ["fury"]
        actions = [action for action in rules.legal_actions(state)
                   if action.kind == "play_gear"]
        self.assertEqual(len(actions), 2)
        rules.apply(state, actions[0], random.Random(273))
        self.assertTrue(state["players"][0].get("ornns_forge_used"))

    def test_batch_power_nexus_uses_four_rainbow_power_optional_score(self):
        deck = legal_deck("SFD-003-221", "OGN-253", "OGN-027")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(274))
        state["fields"][0]["code"] = "SFD-214-221"
        state["fields"][0]["controller"] = 0
        state["players"][0]["power"] = ["any"] * 4
        state["scored"] = [[], []]
        points = state["points"][0]
        rules._score(state, 0, 0, "hold", random.Random(275))
        self.assertEqual(state["optional"][0]["effect"], "power_nexus_score")
        optional = state["optional"][0]
        rules.apply(state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(276))
        self.assertEqual(state["points"][0], points + 2)
        self.assertEqual(state["players"][0]["power"], [])

    def test_batch_chem_baroness_and_gold_use_the_same_optional_resource_path(self):
        deck = legal_deck("SFD-081-221", "OGN-265", "OGN-117")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(277))
        state["players"][0]["legend"] = "SFD-201-221"
        state["players"][0]["legend_exhausted"] = False
        state["fields"][0]["controller"] = 0
        state["scored"] = [[], []]
        rules._score(state, 0, 0, "hold", random.Random(278))
        self.assertEqual(state["optional"][0]["effect"], "chem_baroness_gold")
        optional = state["optional"][0]
        rules.apply(state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(279))
        self.assertTrue(state["players"][0]["legend_exhausted"])
        gold = next(gear for gear in state["players"][0]["gear"] if gear["code"] == "SFD-T03")
        gold["exhausted"] = False
        state["phase"], state["actor"] = "main", 0
        state["points"][0] = state["victory"] - 3
        state["players"][0]["energy"] = 0
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "gear_resource" and
                      __import__("json").loads(action.arguments)["gear"] == gold["id"])
        self.assertEqual(__import__("json").loads(action.arguments)["energy"], 2)
        rules.apply(state, action, random.Random(280))
        self.assertEqual(state["players"][0]["energy"], 2)
        self.assertTrue(gold["exhausted"])

    def test_batch_emperor_of_the_sands_uses_shared_legend_resource_action(self):
        deck = legal_deck("OGN-066", "OGN-261", "OGN-079")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(282))
        state["players"][0]["legend"] = "SFD-197-221"
        state.update(phase="main", actor=0)
        state["players"][0]["energy"] = 1
        self.assertFalse(any(action.kind == "legend_sand_soldier"
                             for action in rules.legal_actions(state)))
        state["players"][0]["gear_played_turn"] = 1
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "legend_sand_soldier")
        rules.apply(state, action, random.Random(283))
        self.assertEqual(state["players"][0]["energy"], 0)
        self.assertTrue(state["players"][0]["legend_exhausted"])
        self.assertEqual([(u["code"], u["location"]) for u in state["units"]],
                         [("SFD-T04", "base:0")])

    def test_batch_battle_mistress_recycle_and_enemy_death_triggers(self):
        deck = legal_deck("OGN-148", "OGN-267", "OGN-162")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(284))
        state["players"][0]["legend"] = "SFD-203-221"
        state.update(phase="main", actor=0)
        state["players"][0]["runes"] = [{"id": "r0", "code": "OGN-007", "exhausted": False}]
        state["players"][0]["rune_deck"] = [{"id": "r1", "code": "OGN-007", "exhausted": False}]
        rules.apply(state, Action.make("recycle_rune", rune="r0"), random.Random(285))
        optional = state["optional"][0]
        self.assertEqual(optional["effect"], "battle_mistress_gold")
        rules.apply(state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(286))
        self.assertTrue(state["players"][0]["legend_exhausted"])
        self.assertEqual(sum(g["code"] == "SFD-T03" for g in state["players"][0]["gear"]), 1)
        state["players"][0]["legend_exhausted"] = True
        victim = rules._new_unit(state, "OGN-001", 1, 0, exhausted=False)
        victim["damage"] = rules.might(state, victim)
        rules._cleanup(state, random.Random(287))
        self.assertFalse(state["players"][0]["legend_exhausted"])

    def test_batch_grand_duelist_uses_mighty_transition_optional(self):
        deck = legal_deck("OGN-151", "OGN-269", "OGN-164")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(288))
        state["players"][0]["legend"] = "SFD-205-221"
        state.update(phase="main", actor=0)
        state["players"][0]["rune_deck"] = [{"id": "r0", "code": "OGN-007", "exhausted": False}]
        unit = rules._new_unit(state, "OGN-001", 0, 0, exhausted=False)
        unit["buff"] = 3
        rules._cleanup(state, random.Random(289))
        optional = state["optional"][0]
        self.assertEqual(optional["effect"], "grand_duelist_channel")
        rules.apply(state, Action.make("optional_effect", optional=optional["id"], accept=True), random.Random(290))
        self.assertTrue(state["players"][0]["legend_exhausted"])
        self.assertEqual(len(state["players"][0]["runes"]), 1)
        self.assertTrue(state["players"][0]["runes"][0]["exhausted"])

    def test_batch_void_drone_reduces_only_non_hand_free_play(self):
        deck = legal_deck("SFD-010-221", "OGN-253", "OGN-027")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(291))
        state.update(phase="main", actor=0)
        card = move_code_to_hand(state, 0, "SFD-010-221")
        state["players"][0]["hand"].remove(card)
        state["players"][0]["trash"].append(card)
        state["players"][0]["energy"] = 1
        state["players"][0]["power"] = ["fury"] * 3
        rules._free_play_revealed_card(state, 0, card, None, random.Random(292))
        self.assertEqual(state["players"][0]["energy"], 0)
        self.assertEqual([(u["code"], u["location"]) for u in state["units"]],
                         [("SFD-010-221", "base:0")])

    def test_batch_black_market_broker_triggers_for_hidden_spell_play(self):
        deck = legal_deck("SFD-121-221", "OGN-267", "OGN-162")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(293))
        state.update(phase="main", actor=0)
        broker = rules._new_unit(state, "SFD-121-221", 0, "base:0", exhausted=False)
        card = "p0:hidden-fight"
        state["cards"][card] = {"code": "OGN-168", "owner": 0}
        state["players"][0]["hand"].append(card)
        target = rules._new_unit(state, "OGN-001", 0, 0, exhausted=False)
        state["players"][0]["energy"] = 2
        state["players"][0]["power"] = ["chaos"]
        rules.apply(state, Action.make(
            "play_spell", card=card, targets=[target["id"]], destination=None,
            spend_buff=None, payment=[0], ignore_cost=False, ignore_energy=False,
            hidden_field=0), random.Random(294))
        self.assertTrue(any(item["effect"] == "gold_on_hidden_play"
                            for item in state["chain"]))
        rules.apply(state, Action.make("pass"), random.Random(295))
        rules.apply(state, Action.make("pass"), random.Random(296))
        self.assertEqual(sum(g["code"] == "SFD-T03" for g in state["players"][0]["gear"]), 1)

    def test_batch_drag_under_uses_registered_field_kill_target_window(self):
        deck = legal_deck("SFD-164-221", "OGN-261", "OGN-079")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(297))
        state.update(phase="main", actor=0)
        card = move_code_to_hand(state, 0, "SFD-164-221")
        target = rules._new_unit(state, "OGN-001", 1, 0, exhausted=False)
        state["players"][0]["energy"] = 5
        action = next(action for action in rules.legal_actions(state)
                      if action.kind == "play_spell_targeted"
                      and __import__("json").loads(action.arguments)["card"] == card)
        rules.apply(state, action, random.Random(298))
        self.assertEqual(state["decision"]["targets"], [target["id"]])
        rules.apply(state, Action.make("choose_target", target=target["id"]), random.Random(299))
        rules.apply(state, Action.make("pass"), random.Random(300))
        rules.apply(state, Action.make("pass"), random.Random(301))
        self.assertNotIn(target, state["units"])

    def test_batch_irelia_fervent_reuses_choice_and_ready_trigger_paths(self):
        deck = legal_deck("OGN-066", "OGN-261", "OGN-079")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(302))
        state.update(phase="main", actor=0)
        source = rules._new_unit(state, "SFD-057-221", 0, 0, exhausted=False)
        self.assertEqual(rules._deflect(state, source), 1)
        triggers = rules._spell_choice_triggers(
            state, 0, {"targets": []}, [source["id"]])
        self.assertEqual(triggers[0]["effect"], "irelia_fervent")
        rules._triggers(state, triggers)
        rules.apply(state, Action.make("pass"), random.Random(303))
        rules.apply(state, Action.make("pass"), random.Random(304))
        self.assertEqual(source["temporary"], 1)
        source["temporary"] = 0
        source["exhausted"] = True
        rules._ready_unit(state, source)
        rules._cleanup(state, random.Random(305))
        self.assertEqual(state["phase"], "chain")
        rules.apply(state, Action.make("pass"), random.Random(306))
        rules.apply(state, Action.make("pass"), random.Random(307))
        self.assertEqual(source["temporary"], 1)

    def test_batch_ravenbloom_conservatory_uses_public_defense_reveal(self):
        deck = legal_deck("SFD-081-221", "OGN-265", "OGN-117")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(281))
        card = "p1:conservatory-spell"
        state["cards"][card] = {"code": "SFD-087-221", "owner": 1}
        state["players"][1]["main"].insert(0, card)
        state.update(phase="main", actor=1)
        item = {"effect": "ravenbloom_conservatory", "owner": 1}
        self.assertFalse(rules._effect_ravenbloom_conservatory(state, item, random.Random(282)))
        self.assertEqual(state["phase"], "reveal")
        self.assertEqual(state["actor"], 0)
        rules.apply(state, Action.make("end_reveal"), random.Random(283))
        self.assertIn(card, state["players"][1]["hand"])
        self.assertNotIn(card, state["players"][1]["main"])

    def test_batch_glasc_deathknell_replays_eligible_trash_unit_for_free(self):
        deck = legal_deck("SFD-165-221", "OGN-261", "OGN-079")
        rules = SpiritforgedRules([deck, deck])
        state = rules.initial_state(random.Random(306))
        state.update(phase="main", actor=0)
        row = state["players"][0]
        candidate = next(
            uid for uid in row["main"]
            if rules.cards[state["cards"][uid]["code"]]["type"] == "unit"
            and rules.cards[state["cards"][uid]["code"]]["energy"] <= 3
            and rules.cards[state["cards"][uid]["code"]]["power_cost"] <= 1)
        row["main"].remove(candidate)
        row["trash"].append(candidate)
        glasc = rules._new_unit(state, "SFD-165-221", 0, "base:0", exhausted=False)
        glasc["damage"] = rules.might(state, glasc)
        rules._cleanup(state, random.Random(307))
        optional = next(item for item in state["optional"]
                        if item["effect"] == "replay_trash_unit")
        self.assertEqual(optional["max_energy"], 3)
        self.assertEqual(optional["max_power"], 1)
        rules.apply(state, Action.make("optional_effect", optional=optional["id"], accept=True),
                    random.Random(308))
        self.assertEqual(state["phase"], "reveal")
        self.assertEqual(state["reveal"]["choices"], [candidate])
        rules.apply(state, Action.make("choose_revealed", card=candidate), random.Random(309))
        rules.apply(state, Action.make("confirm_revealed"), random.Random(310))
        self.assertNotIn(candidate, row["trash"])
        self.assertTrue(any(unit["card"] == candidate for unit in state["units"]))
        self.assertIsNone(state.get("reveal"))
        rules.validate(state)


if __name__ == "__main__":
    unittest.main()
