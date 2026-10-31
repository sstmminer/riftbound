"""Detailed, deterministic checks for cross-zone and nested-resolution paths.

These tests intentionally inspect both the private rules state and the public
observation.  They are a small executable trace for the GUI: every target
window must expose the complete legal candidate set to the acting player,
hide the decision from the opponent, and keep the live Chain visible.
"""

import json
import random
import unittest

from riftbound.engine import Action
from riftbound.origins import OriginsRules


class CrossRegionInteractionTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(101))
        self.state.update(phase="main", actor=0, turn_player=0, turn=3)
        for row in self.state["players"]:
            row["energy"] = 20
            row["power"] = ["fury"] * 20

    def card(self, player, code, zone="main"):
        row = self.state["players"][player]
        uid = row[zone].pop()
        self.state["cards"][uid]["code"] = code
        return uid

    def unit(self, player, code="OGN-219", location=0, *, card=True):
        uid = self.card(player, code) if card else None
        return self.rules._new_unit(
            self.state, code, player, location, card=uid, exhausted=False)

    def apply(self, kind, **kwargs):
        actions = [a for a in self.rules.legal_actions(self.state)
                   if a.kind == kind
                   and all(json.loads(a.arguments).get(key) == value
                           for key, value in kwargs.items())]
        self.assertTrue(actions, (kind, kwargs, self.state["phase"], self.state.get("decision")))
        self.rules.apply(self.state, actions[0], random.Random(101))
        self.rules.validate(self.state)

    def close_chain(self):
        for _ in range(80):
            if self.state["phase"] not in {"chain", "trigger_order"}:
                return
            if self.state["phase"] == "trigger_order":
                self.apply("order_triggers")
            else:
                self.apply("pass")
        self.fail("chain did not close")

    def snapshot(self, player=0):
        observation = self.rules.observe(self.state, player)
        decision = observation.get("decision") or {}
        return {
            "phase": observation.get("phase"),
            "actor": observation.get("actor"),
            "chain": [(item.get("effect"), item.get("code"), item.get("owner"))
                      for item in observation.get("chain", [])],
            "decision": {
                "kind": decision.get("kind"),
                "player": decision.get("player"),
                "targets": list(decision.get("targets", [])),
            } if decision else None,
        }

    def test_control_change_keeps_physical_card_owner_across_recall_and_death(self):
        spell = self.card(0, "OGN-203")
        self.state["players"][0]["hand"].append(spell)
        enemy = self.unit(1, location=0)
        self.state["fields"][0]["controller"] = 1

        self.rules.apply(self.state, Action.make(
            "play_spell", card=spell, targets=[enemy["id"]],
            destination=None, spend_buff=None, payment=[], ignore_cost=True),
            random.Random(101))
        self.close_chain()

        self.assertEqual(enemy["owner"], 0)
        self.assertEqual(enemy["card_owner"], 1)
        self.assertEqual(enemy["location"], "base:0")
        enemy["damage"] = self.rules.might(self.state, enemy)
        self.rules._cleanup(self.state, random.Random(101))
        self.assertNotIn(enemy, self.state["units"])
        self.assertIn(enemy["card"], self.state["players"][1]["trash"])
        self.assertNotIn(enemy["card"], self.state["players"][0]["trash"])

    def test_nested_free_play_keeps_parent_chain_and_exposes_target_then_payment(self):
        card = self.card(0, "OGN-009")
        self.state["players"][0]["banishment"].append(card)
        target = self.unit(1, location=0)
        parent = {"effect": "spell", "owner": 0, "code": "OGN-115", "card": None}
        self.state["chain"].append(parent)
        self.state["phase"], self.state["actor"] = "chain", 0

        self.rules._free_play_revealed_card(
            self.state, 0, card, parent, random.Random(101),
            ignore_energy=True, card_owner=0)
        trace = self.snapshot(0)
        self.assertEqual(trace["decision"]["kind"], "target")
        self.assertEqual(trace["decision"]["targets"], [target["id"]])
        self.assertIsNone(self.snapshot(1)["decision"])
        self.assertIn(("spell", "OGN-115", 0), trace["chain"])

        self.apply("choose_target", target=target["id"])
        self.assertEqual(self.state["decision"]["kind"], "free_play_payment")
        self.apply("choose_payment", payment=self.state["decision"]["payments"][0])
        self.assertEqual(self.state["chain"][-1]["targets"], [target["id"]])
        self.assertEqual(self.state["chain"][-2]["code"], "OGN-115")

    def test_recycle_event_exposes_karma_target_and_hides_it_from_opponent(self):
        karma_card = self.card(0, "OGN-235")
        karma = self.rules._new_unit(
            self.state, "OGN-235", 0, "base:0", card=karma_card, exhausted=False)
        target = self.unit(0, location=0)
        recycled = self.card(0, "OGN-009")
        self.state["players"][0]["trash"].append(recycled)

        self.rules._recycle_cards_to_main(
            self.state, 0, [recycled], source="trash", rng=random.Random(101))
        trace = self.snapshot(0)
        self.assertEqual(trace["decision"]["kind"], "target")
        self.assertEqual(set(trace["decision"]["targets"]), {karma["id"], target["id"]})
        self.assertIsNone(self.snapshot(1)["decision"])
        self.apply("choose_target", target=target["id"])
        self.close_chain()
        self.assertEqual(target["buff"], 1)
        self.assertIn(recycled, self.state["players"][0]["main"])

    def test_jinx_discard_trigger_and_battlefield_optional_target_are_visible(self):
        jinx_card = self.card(0, "OGN-202")
        jinx = self.rules._new_unit(
            self.state, "OGN-202", 0, "base:0", card=jinx_card, exhausted=True)
        discarded = self.card(0, "OGN-009")
        self.state["players"][0]["trash"].append(discarded)
        self.rules._trigger_jinx_discard(self.state, 0)
        self.assertEqual(self.state["chain"][-1]["effect"], "jinx_discard")
        self.close_chain()
        self.assertFalse(jinx["exhausted"])
        self.assertEqual(jinx["temporary"], 1)

        self.state["fields"][0]["code"] = "OGN-283"
        self.state["fields"][0]["controller"] = 0
        first = self.unit(0, location=0)
        second = self.unit(0, location=0)
        self.rules._score(self.state, 0, 0, "hold", random.Random(101))
        trace = self.snapshot(0)
        self.assertEqual(trace["decision"]["kind"], "target")
        self.assertEqual(set(trace["decision"]["targets"]), {first["id"], second["id"]})
        self.assertIsNone(self.snapshot(1)["decision"])
        self.apply("choose_target", target=second["id"])
        self.assertEqual(second["buff"], 1)


if __name__ == "__main__":
    unittest.main()
