import unittest
import json
import random

from riftbound.abilities import AbilityRegistry, AbilitySpec, ORIGINS_ABILITIES
from riftbound.origins import OriginsRules


class AbilityRegistryTests(unittest.TestCase):
    def test_origins_registry_exposes_e_abilities_by_source(self):
        caitlyn = ORIGINS_ABILITIES.copyable_for_heimer("unit", "OGN-068")
        self.assertEqual([spec.ability_id for spec in caitlyn], ["unit.caitlyn_damage"])

        legend = ORIGINS_ABILITIES.copyable_for_heimer("legend", "OGN-257")
        self.assertEqual([spec.ability_id for spec in legend], ["legend.blind_monk_buff"])

        gear = ORIGINS_ABILITIES.copyable_for_heimer("gear", "OGN-023")
        self.assertEqual([spec.ability_id for spec in gear], ["gear.unlicensed_armory_protect"])

        # These two Gear abilities are easy to miss because their existing
        # resolvers historically lived outside the Heimer path.
        self.assertEqual(
            [spec.ability_id for spec in ORIGINS_ABILITIES.copyable_for_heimer("gear", "OGN-017")],
            ["gear.iron_ballista_damage"],
        )
        self.assertEqual(
            [spec.ability_id for spec in ORIGINS_ABILITIES.copyable_for_heimer("gear", "OGN-181")],
            ["gear.pack_of_wonders_return"],
        )

    def test_heimer_filter_excludes_non_exhaust_abilities(self):
        for source_kind, code in (
            ("unit", "OGN-036"),   # Vi: recycle from trash, no [E]
            ("unit", "OGN-157"),   # Udyr: spend a Buff, no [E]
            ("unit", "OGN-194"),   # Nocturne: top-deck replacement, no [E]
            ("gear", "OGN-077"),   # Zhonya: Hidden/death replacement, no [E]
        ):
            self.assertEqual(ORIGINS_ABILITIES.copyable_for_heimer(source_kind, code), ())

        # Non-E metadata remains available to the ordinary rules layer.
        nocturne = ORIGINS_ABILITIES.for_source("unit", "OGN-194")
        self.assertEqual([spec.ability_id for spec in nocturne], ["unit.nocturne_ganking"])
        self.assertFalse(nocturne[0].copyable)
        self.assertEqual(ORIGINS_ABILITIES.copyable_for_heimer("gear", "OGN-212"), ())

    def test_every_copyable_spec_requires_exhaust(self):
        for spec in ORIGINS_ABILITIES.all():
            if spec.copyable:
                self.assertTrue(spec.requires_exhaust, spec.ability_id)

    def test_registry_rejects_inconsistent_copyability(self):
        with self.assertRaisesRegex(ValueError, "without exhaust"):
            AbilitySpec(
                ability_id="future.invalid_copy",
                source_kind="unit",
                source_codes=frozenset({"OGN-999"}),
                requires_exhaust=False,
                action_kind="future_action",
                copyable_by_heimer=True,
            )

    def test_future_registered_e_ability_is_automatically_copyable(self):
        registry = AbilityRegistry()
        registry.register(AbilitySpec(
            ability_id="future.example_exhaust",
            source_kind="unit",
            source_codes=frozenset({"OGN-999"}),
            requires_exhaust=True,
            action_kind="future_action",
        ))
        self.assertEqual(
            [spec.ability_id for spec in registry.copyable_for_heimer("unit", "OGN-999")],
            ["future.example_exhaust"],
        )

    def test_registry_serialization_contains_resolution_metadata(self):
        rows = ORIGINS_ABILITIES.as_dict()
        self.assertTrue(rows)
        row = next(item for item in rows if item["ability_id"] == "gear.unlicensed_armory_protect")
        self.assertTrue(row["requires_exhaust"])
        self.assertEqual(row["action_kind"], "gear_armory_protect")
        self.assertEqual(row["target_mode"], "friendly_unit")

    def test_heimer_discovers_registered_e_abilities_and_excludes_non_e(self):
        rules = OriginsRules()
        state = rules.initial_state(random.Random(19))
        state.update(phase="main", actor=0, turn_player=0, turn=3)
        state["players"][0]["energy"] = 10
        state["players"][0]["power"] = ["fury"] * 4
        state["players"][0]["legend"] = "OGN-257"
        heimer = rules._new_unit(state, "OGN-111", 0, 0, exhausted=False)
        rules._new_unit(state, "OGN-068", 0, 0, exhausted=False)
        enemy = rules._new_unit(state, "OGN-003", 1, 0, exhausted=False)
        rules._new_unit(state, "OGN-194", 0, 0, exhausted=False)
        state["players"][0]["gear"].extend([
            {"id": "gear:090", "card": None, "code": "OGN-090", "owner": 0,
             "location": "base:0", "exhausted": False},
            {"id": "gear:077", "card": None, "code": "OGN-077", "owner": 0,
             "location": "base:0", "exhausted": False},
        ])

        copied = [a for a in rules.legal_actions(state)
                  if a.kind in {"ability_activate", "ability_targeted"}
                  and json.loads(a.arguments).get("source") == heimer["id"]]
        copied_ids = {json.loads(a.arguments)["ability_id"] for a in copied}
        self.assertIn("unit.caitlyn_damage", copied_ids)
        self.assertIn("legend.blind_monk_buff", copied_ids)
        self.assertIn("gear.orb_of_regret_debuff", copied_ids)
        self.assertNotIn("unit.vi_recycle_buff", copied_ids)
        self.assertNotIn("unit.udyr_choice", copied_ids)
        self.assertNotIn("unit.nocturne_ganking", copied_ids)
        self.assertNotIn("gear.zhonya_death_replacement", copied_ids)
        self.assertFalse(rules._heimer_has_copy(state, 0, "gear", "OGN-072"))
        state["players"][0]["gear"].append(
            {"id": "gear:072", "card": None, "code": "OGN-072", "owner": 0,
             "location": "base:0", "exhausted": False})
        self.assertTrue(rules._heimer_has_copy(state, 0, "gear", "OGN-072"))

        debuff = next(a for a in copied
                      if a.kind == "ability_targeted"
                      and json.loads(a.arguments)["ability_id"] == "gear.orb_of_regret_debuff")
        rules.apply(state, debuff, random.Random(23))
        choose = next(a for a in rules.legal_actions(state)
                      if a.kind == "choose_target" and enemy["id"] in a.arguments)
        rules.apply(state, choose, random.Random(23))
        self.assertEqual(enemy["temporary"], -1)
        self.assertTrue(heimer["exhausted"])


if __name__ == "__main__":
    unittest.main()
