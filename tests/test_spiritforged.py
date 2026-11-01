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
        self.assertEqual(len(registry.executable_codes()), 85)
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
        self.assertEqual(registry.get("SFD-069-221").conquer_effect, "play_gold_gear")
        self.assertEqual(registry.get("SFD-074-221").entry_trigger, "optional_kill_cheap_gear")
        self.assertEqual(registry.get("SFD-075-221").global_effect, "prize_progress")
        self.assertEqual(registry.get("SFD-091-221").entry_trigger, "optional_draw_or_buff")
        self.assertEqual(registry.get("SFD-149-221").entry_trigger, "discard_one_draw_two")
        self.assertEqual(registry.get("SFD-157-221").entry_trigger, "play_sand_soldier")
        self.assertEqual(registry.get("SFD-162-221").spell_effect, "kill_small_unit_and_gold")
        self.assertEqual(registry.get("SFD-162-221").target_scope, "field_unit_might_le_2")
        self.assertEqual(registry.get("SFD-175-221").entry_trigger, "buff_other_units_two")
        self.assertEqual(registry.get("SFD-179-221").move_effect, "play_recruit_three")
        self.assertEqual(registry.behavior_id("SFD-222-221"), "OGN-040")
        self.assertIsNone(registry.get("SFD-002-221"))

    def test_unregistered_sfd_card_is_rejected(self):
        deck = legal_deck("SFD-002-221", "OGN-247", "OGN-039")
        with self.assertRaises(RulesUnavailable):
            SpiritforgedRules([deck, deck])

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


if __name__ == "__main__":
    unittest.main()
