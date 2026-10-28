import random
import unittest

from riftbound.origins import OriginsRules


class GearBatchTests(unittest.TestCase):
    def setUp(self):
        self.rules = OriginsRules()
        self.state = self.rules.initial_state(random.Random(71))
        self.state.update(phase="main", actor=0, turn_player=0, turn=2)
        self.state["players"][0]["energy"] = 20
        self.state["players"][0]["power"] = ["fury", "calm", "mind", "body", "chaos", "order"] * 2

    def card(self, code):
        row = self.state["players"][0]
        uid = next(uid for uid in row["main"] if self.state["cards"][uid]["code"] == "OGN-219")
        row["main"].remove(uid)
        self.state["cards"][uid]["code"] = code
        row["hand"].append(uid)
        return uid

    def play(self, code):
        uid = self.card(code)
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "play_gear" and uid in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.rules.validate(self.state)
        return uid

    def test_gear_enters_ready_at_controller_base(self):
        uid = self.play("OGN-040")
        gear = self.state["players"][0]["gear"][-1]
        self.assertEqual((gear["card"], gear["location"], gear["exhausted"]), (uid, "base:0", False))

    def test_resource_seals_and_energy_conduit_activate(self):
        self.play("OGN-040")
        before = len(self.state["players"][0]["power"])
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "gear_resource" and '"domain":"fury"' in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.assertEqual(len(self.state["players"][0]["power"]), before + 1)
        self.play("OGN-098")
        before_energy = self.state["players"][0]["energy"]
        action = next(a for a in self.rules.legal_actions(self.state)
                      if a.kind == "gear_resource" and '"energy":1' in a.arguments)
        self.rules.apply(self.state, action, random.Random(4))
        self.assertEqual(self.state["players"][0]["energy"], before_energy + 1)

    def test_iron_ballista_enters_exhausted(self):
        self.play("OGN-017")
        self.assertTrue(self.state["players"][0]["gear"][-1]["exhausted"])

    def test_scrapheap_play_draws_and_forge_creates_recruit(self):
        before = len(self.state["players"][0]["hand"])
        self.play("OGN-182")
        self.assertEqual(len(self.state["players"][0]["hand"]), before + 1)
        self.play("OGN-212")
        self.assertTrue(any(u["code"] == "OGN-273" and u["owner"] == 0
                            for u in self.state["units"]))


if __name__ == "__main__":
    unittest.main()
