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
        self.assertEqual(len(registry.executable_codes()), 29)
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


if __name__ == "__main__":
    unittest.main()
