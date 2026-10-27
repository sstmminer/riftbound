import random
import unittest

from riftbound.origins import OriginsRules
from riftbound.support import FIELD_CODES, TOKEN, starter_deck


class HeraldOfTheArcaneTests(unittest.TestCase):
    def test_herald_recruits_into_base_for_one_energy(self):
        deck = starter_deck()
        deck["battlefields"] = sorted(FIELD_CODES)[:3]
        rules = OriginsRules([deck, deck])
        state = rules.initial_state(random.Random(4))
        state.update(phase="main", actor=0, turn_player=0, turn=2)
        row = state["players"][0]
        row["legend"] = "OGN-265"
        row["energy"] = 1
        before = len(rules._units(state, 0, "base:0"))
        action = next(a for a in rules.legal_actions(state) if a.kind == "legend_recruit")

        rules.apply(state, action, random.Random(5))

        self.assertEqual(row["energy"], 0)
        self.assertTrue(row["legend_exhausted"])
        recruits = [u for u in rules._units(state, 0, "base:0") if u["code"] == TOKEN]
        self.assertEqual(len(recruits), before + 1)
        self.assertTrue(recruits[-1]["exhausted"])
        self.assertFalse(any(a.kind == "legend_recruit" for a in rules.legal_actions(state)))

    def test_herald_requires_energy_and_ready_legend(self):
        deck = starter_deck()
        deck["battlefields"] = sorted(FIELD_CODES)[:3]
        rules = OriginsRules([deck, deck])
        state = rules.initial_state(random.Random(5))
        state.update(phase="main", actor=0, turn_player=0, turn=2)
        row = state["players"][0]
        row["legend"] = "OGN-265"
        row["energy"] = 0
        self.assertFalse(any(a.kind == "legend_recruit" for a in rules.legal_actions(state)))
        row["energy"] = 1
        row["legend_exhausted"] = True
        self.assertFalse(any(a.kind == "legend_recruit" for a in rules.legal_actions(state)))


class NineTailedFoxTests(unittest.TestCase):
    def test_nine_tailed_fox_reduces_enemy_attack_at_controlled_field(self):
        deck = starter_deck()
        deck["battlefields"] = sorted(FIELD_CODES)[:3]
        rules = OriginsRules([deck, deck])
        state = rules.initial_state(random.Random(6))
        state.update(phase="showdown", actor=0, turn_player=0, turn=2)
        state["players"][1]["legend"] = "OGN-255"
        state["fields"][0]["controller"] = 1
        attacker = rules._new_unit(state, "OGN-219", 0, 0, exhausted=False)
        defender = rules._new_unit(state, "OGN-219", 1, 0, exhausted=False)
        state["battle"] = {"field": 0, "attacker": 0, "combat": True}

        rules._close_showdown(state, random.Random(7))

        self.assertEqual(attacker["temporary"], -1)
        self.assertEqual(state["phase"], "damage")
        self.assertGreaterEqual(rules.might(state, attacker), 1)


class RelentlessStormTests(unittest.TestCase):
    def test_relentless_storm_channels_an_exhausted_rune_after_mighty_play(self):
        deck = starter_deck()
        deck["battlefields"] = sorted(FIELD_CODES)[:3]
        rules = OriginsRules([deck, deck])
        state = rules.initial_state(random.Random(8))
        state.update(phase="main", actor=0, turn_player=0, turn=2)
        row = state["players"][0]
        row["legend"] = "OGN-249"
        unit = rules._new_unit(state, "OGN-223", 0, "base:0", exhausted=False)
        state["legend_options"] = [{"owner": 0, "source": unit["id"]}]
        before = len(row["rune_deck"])

        action = next(a for a in rules.legal_actions(state) if a.kind == "legend_channel")
        rules.apply(state, action, random.Random(9))

        self.assertTrue(row["legend_exhausted"])
        self.assertEqual(len(row["rune_deck"]), before - 1)
        self.assertTrue(row["runes"][-1]["exhausted"])
        self.assertEqual(state["legend_options"], [])

