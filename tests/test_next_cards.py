import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class NextCardBatchTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(77))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["order"] * 8
        self.state["fields"][0]["controller"] = 0

    def give(self, code):
        row = self.state["players"][0]
        uid = row["main"].pop()
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def test_pakaa_hidden_and_bandle_tree_two_slots(self):
        first = self.give("OGN-135")
        actions = [a for a in self.rules.legal_actions(self.state)
                   if a.kind == "hide_card" and first in a.arguments]
        self.assertTrue(actions)
        self.rules.apply(self.state, actions[0], random.Random(1))
        second = self.give("OGN-135")
        self.state["fields"][0]["code"] = "OGN-278"
        actions = [a for a in self.rules.legal_actions(self.state)
                   if a.kind == "hide_card" and second in a.arguments]
        self.assertTrue(actions)

    def test_noxus_saboteur_blocks_opponent_hidden(self):
        saboteur = self.rules._new_unit(self.state, "OGN-018", 1, 0, exhausted=False)
        card = self.give("OGN-135")
        # Saboteur does not prevent placing a facedown card; it prevents that
        # opponent's later reveal/play at this battlefield.
        hide = next(a for a in self.rules.legal_actions(self.state)
                    if a.kind == "hide_card" and card in a.arguments)
        self.rules.apply(self.state, hide, random.Random(1))
        self.state["turn"] = 3
        self.assertFalse(any(a.kind.startswith("play_hidden") and card in a.arguments
                             for a in self.rules.legal_actions(self.state)))
        self.state["units"].remove(saboteur)

    def test_swift_scout_returns_teemo(self):
        self.state["players"][0]["legend"] = "OGN-263"
        teemo_card = self.give("OGN-121")
        unit = self.rules._new_unit(self.state, "OGN-121", 0, 0, card=teemo_card, exhausted=False)
        self.state["players"][0]["hand"].remove(teemo_card)
        self.state["players"][0]["energy"] = 1
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "legend_teemo" and unit["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        self.assertNotIn(unit, self.state["units"])
        self.assertIn(teemo_card, self.state["players"][0]["hand"])

    def test_guillotine_marks_target_until_next_damage(self):
        card = self.give("OGN-254")
        target = self.rules._new_unit(self.state, "OGN-219", 1, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_spell" and card in a.arguments and target["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        for _ in range(4):
            if self.state["phase"] not in {"chain", "showdown"}:
                break
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(1))
        self.assertEqual(target.get("kill_on_damage"), self.state["turn"])
        self.rules._deal_damage(self.state, target, 1)
        self.rules._cleanup(self.state, random.Random(1))
        self.assertNotIn(target, self.state["units"])

    def test_kinkou_monk_requires_explicit_up_to_two_targets(self):
        card = self.give("OGN-141")
        self.state["players"][0]["power"] = ["body"] * 8
        first = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_unit" and card in a.arguments and '"location":0' in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        self.assertEqual(self.state["phase"], "decision")
        self.assertTrue(any(a.kind == "choose_target" and first["id"] in a.arguments
                            for a in self.rules.legal_actions(self.state)))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "choose_target" and first["id"] in a.arguments),
                         random.Random(1))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "choose_target" and second["id"] in a.arguments),
                         random.Random(1))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "confirm_targets"),
                         random.Random(1))
        self.assertEqual(self.state["chain"][-1]["targets"], [first["id"], second["id"]])

    def test_wildclaw_shaman_confirms_then_selects_buff_to_spend(self):
        card = self.give("OGN-147")
        self.state["players"][0]["power"] = ["body"] * 8
        buffed = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        buffed["buff"] = 1
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_unit" and card in a.arguments and '"location":0' in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        for _ in range(2):
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(1))
        self.assertEqual(self.state["phase"], "optional")
        self.assertTrue(any(a.kind == "optional_effect" and '"accept":true' in a.arguments
                            for a in self.rules.legal_actions(self.state)))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "optional_effect" and '"accept":true' in a.arguments),
                         random.Random(1))
        self.assertEqual(self.state["phase"], "decision")
        self.assertEqual(self.state["decision"]["targets"], [buffed["id"]])
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "choose_target" and buffed["id"] in a.arguments),
                         random.Random(1))
        shaman = next(u for u in self.state["units"] if u["code"] == "OGN-147")
        self.assertEqual(buffed["buff"], 0)
        self.assertEqual(shaman["buff"], 1)
        self.assertFalse(shaman["exhausted"])

    def test_albus_confirms_multiple_buff_targets_and_channels(self):
        card = self.give("OGN-230")
        self.state["players"][0]["power"] = ["order"] * 8
        first = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        second = self.rules._new_unit(self.state, "OGN-219", 0, 0, exhausted=False)
        first["buff"], second["buff"] = 1, 1
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_unit" and card in a.arguments and '"location":0' in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        for _ in range(2):
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(1))
        self.assertEqual(self.state["phase"], "optional")
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "optional_effect" and '"accept":true' in a.arguments),
                         random.Random(1))
        self.assertEqual(self.state["phase"], "decision")
        for target in (first, second):
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state)
                                  if a.kind == "choose_target" and target["id"] in a.arguments),
                             random.Random(1))
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "confirm_targets"),
                         random.Random(1))
        self.assertEqual(first["buff"], 0)
        self.assertEqual(second["buff"], 0)
        self.assertEqual(len(self.state["players"][0]["runes"]), 2)

    def test_jinx_discard_event_resolves_once_on_chain(self):
        jinx = self.rules._new_unit(self.state, "OGN-202", 0, 0, exhausted=True)
        self.rules._trigger_jinx_discard(self.state, 0)
        self.assertEqual(self.state["phase"], "chain")
        self.assertEqual(sum(item["effect"] == "jinx_discard" for item in self.state["chain"]), 1)
        for _ in range(2):
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(1))
        self.assertFalse(jinx["exhausted"])
        self.assertEqual(jinx["temporary"], 1)

    def test_karma_recycle_event_requires_a_friendly_target(self):
        karma = self.rules._new_unit(self.state, "OGN-235", 0, 0, exhausted=False)
        vi = self.rules._new_unit(self.state, "OGN-036", 0, 0, exhausted=False)
        recycled = self.state["players"][0]["main"].pop()
        self.state["players"][0]["trash"].append(recycled)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "unit_recycle_buff" and vi["id"] in a.arguments)
        self.rules.apply(self.state, action, random.Random(1))
        self.assertEqual(self.state["phase"], "decision")
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "choose_target" and karma["id"] in a.arguments),
                         random.Random(1))
        for _ in range(2):
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(1))
        self.assertEqual(karma["buff"], 1)

    def _resolve_karma_target(self, karma):
        self.assertEqual(self.state["phase"], "decision")
        self.rules.apply(self.state,
                         next(a for a in self.rules.legal_actions(self.state)
                              if a.kind == "choose_target" and karma["id"] in a.arguments),
                         random.Random(1))
        for _ in range(2):
            self.rules.apply(self.state,
                             next(a for a in self.rules.legal_actions(self.state) if a.kind == "pass"),
                             random.Random(1))

    def test_karma_triggers_from_burn_out_recycle(self):
        karma = self.rules._new_unit(self.state, "OGN-235", 0, 0, exhausted=False)
        recycled = self.state["players"][0]["main"].pop()
        self.state["players"][0]["main"] = []
        self.state["players"][0]["trash"].append(recycled)
        self.rules._draw(self.state, 0, 1, random.Random(1))
        self._resolve_karma_target(karma)
        self.assertEqual(karma["buff"], 1)

    def test_karma_triggers_from_vision_recycle(self):
        karma = self.rules._new_unit(self.state, "OGN-235", 0, 0, exhausted=False)
        self.state["phase"], self.state["actor"] = "decision", 0
        self.state["decision"] = {"kind": "predict", "player": 0, "remaining": 1}
        self.rules.apply(self.state, Action.make("predict", recycle=True), random.Random(1))
        self._resolve_karma_target(karma)
        self.assertEqual(karma["buff"], 1)


if __name__ == "__main__":
    unittest.main()
