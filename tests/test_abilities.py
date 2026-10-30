import unittest

from riftbound.abilities import ORIGINS_ABILITIES, AbilitySpec, AbilityRegistry


class AbilityRegistryTests(unittest.TestCase):
    def test_exhaust_boundary_is_explicit(self):
        self.assertTrue(ORIGINS_ABILITIES.copyable_for_heimer("unit", "OGN-068"))
        self.assertTrue(ORIGINS_ABILITIES.copyable_for_heimer("legend", "OGN-257"))
        self.assertTrue(ORIGINS_ABILITIES.copyable_for_heimer("gear", "OGN-023"))
        self.assertEqual(ORIGINS_ABILITIES.copyable_for_heimer("unit", "OGN-036"), ())
        self.assertEqual(ORIGINS_ABILITIES.copyable_for_heimer("unit", "OGN-157"), ())
        self.assertEqual(ORIGINS_ABILITIES.copyable_for_heimer("unit", "OGN-194"), ())
        self.assertEqual(ORIGINS_ABILITIES.copyable_for_heimer("gear", "OGN-077"), ())

    def test_every_exhaust_source_has_serializable_metadata(self):
        specs = [spec for spec in ORIGINS_ABILITIES.all() if spec.requires_exhaust]
        self.assertGreaterEqual(len(specs), 20)
        for spec in specs:
            self.assertTrue(spec.action_kind)
            self.assertTrue(spec.source_codes)
            self.assertTrue(spec.copyable)
            row = next(item for item in ORIGINS_ABILITIES.as_dict()
                       if item["ability_id"] == spec.ability_id)
            self.assertEqual(row["requires_exhaust"], True)
            self.assertEqual(row["copyable_by_heimer"], True)

    def test_registry_rejects_copyable_non_exhaust_ability(self):
        with self.assertRaises(ValueError):
            AbilitySpec("bad", "unit", frozenset({"OGN-001"}), False,
                        "unit_bad", copyable_by_heimer=True)

    def test_registry_rejects_duplicate_ids(self):
        registry = AbilityRegistry()
        spec = AbilitySpec("one", "unit", frozenset({"OGN-001"}), True, "unit_one")
        registry.register(spec)
        with self.assertRaises(ValueError):
            registry.register(spec)


if __name__ == "__main__":
    unittest.main()
