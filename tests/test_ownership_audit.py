import random
import unittest

from riftbound.origins import OriginsRules


class OwnershipAuditTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(901))
        self.state.update(phase="main", actor=0, turn_player=0, turn=3)

    def test_recall_of_possessed_unit_returns_physical_card_to_card_owner(self):
        row = self.state["players"][1]
        card = row["main"].pop()
        self.state["cards"][card]["code"] = "OGN-219"
        unit = self.rules._new_unit(self.state, "OGN-219", 1, 0,
                                    card=card, exhausted=False)
        unit["owner"] = 0
        item = {"code": "OGN-187", "owner": 0, "targets": [unit["id"]],
                "choice_done": True, "card": None}
        self.rules._effect_spell(self.state, item, random.Random(901))
        self.assertNotIn(unit, self.state["units"])
        self.assertIn(card, self.state["players"][1]["hand"])
        self.assertNotIn(card, self.state["players"][0]["hand"])

    def test_cross_controlled_gear_is_trashed_to_physical_owner(self):
        row = self.state["players"][1]
        card = row["main"].pop()
        self.state["cards"][card]["code"] = "OGN-040"
        self.state["players"][0]["gear"].append({
            "id": "cross-gear", "card": card, "code": "OGN-040",
            "owner": 0, "card_owner": 1, "location": "base:0",
            "exhausted": False,
        })
        item = {"code": "OGN-022", "owner": 0, "targets": [],
                "card": None}
        self.rules._effect_spell(self.state, item, random.Random(901))
        self.assertIn(card, self.state["players"][1]["trash"])
        self.assertNotIn(card, self.state["players"][0]["trash"])


if __name__ == "__main__":
    unittest.main()
