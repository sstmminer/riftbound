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

