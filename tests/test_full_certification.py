import unittest

from tools.full_certification import build_certification, catalog_audit, registry_audit


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
        self.assertFalse(report["checks"]["known_blockers_closed"])
        self.assertFalse(report["checks"]["certified"])
        self.assertGreater(len(report["known_blockers"]), 0)


if __name__ == "__main__":
    unittest.main()
