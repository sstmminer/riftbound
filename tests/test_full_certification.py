import unittest

from tools.full_certification import (
    CARD_BEHAVIOR_BLOCKERS,
    CARD_BEHAVIOR_COVERAGE,
    build_certification,
    contract_audit,
    catalog_audit,
    registry_audit,
)


class FullCertificationTests(unittest.TestCase):
    def test_catalog_and_registry_are_structurally_complete(self):
        catalog = catalog_audit()
        registry = registry_audit()
        self.assertTrue(catalog["partition_complete"])
        self.assertEqual(catalog["catalog_cards"], 298)
        self.assertTrue(registry["integrity"])

    def test_certification_does_not_hide_known_rule_limitations(self):
        report = build_certification(seeds=1, max_steps=1,
                                     policies=("greedy",), run_tests=False)
        self.assertTrue(report["checks"]["catalog_partition"])
        self.assertTrue(report["checks"]["ability_registry"])
        self.assertTrue(report["checks"]["contract_invariants"])
        self.assertTrue(report["checks"]["reference_core"])
        self.assertTrue(report["checks"]["reference_production_differential"])
        self.assertFalse(report["checks"]["known_blockers_closed"])
        self.assertTrue(report["checks"]["card_behavior_blockers_closed"])
        self.assertFalse(report["checks"]["certified"])
        self.assertGreater(len(report["known_blockers"]), 0)
        self.assertEqual(report["card_behavior_blockers"], [])
        self.assertEqual(
            {entry["code"] for entry in report["card_behavior_coverage"]},
            {entry["code"] for entry in CARD_BEHAVIOR_COVERAGE},
        )

    def test_independent_contract_audit_passes(self):
        self.assertTrue(contract_audit(seeds=1, steps=20)["passed"])


if __name__ == "__main__":
    unittest.main()
