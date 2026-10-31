import json
import unittest
from pathlib import Path

from tools.differential_certification import certify, run_fixture
from tools.reference_rules import ReferenceRuleError, ReferenceRules


class ReferenceRulesTests(unittest.TestCase):
    def test_golden_core_scenarios_pass(self):
        report = certify(Path(__file__).parent / "golden" / "core_scenarios.json")
        self.assertTrue(report["passed"], report)
        self.assertEqual(len(report["fixtures"]), 7)
        self.assertEqual(report["production_supported"], 7)
        self.assertTrue(report["production_differential_passed"])
        self.assertEqual(report["production_unsupported_count"], 0)

    def test_reference_model_does_not_share_production_imports(self):
        module_text = Path("tools/reference_rules.py").read_text(encoding="utf-8")
        self.assertNotIn("OriginsRules", module_text)
        self.assertNotIn("AbilityRegistry", module_text)

    def test_illegal_priority_and_damage_are_rejected(self):
        rules = ReferenceRules()
        state = rules.initial_state()
        rules.push_chain(state, "spell", 0)
        with self.assertRaises(ReferenceRuleError):
            rules.pass_priority(state, 1)
        with self.assertRaises(ReferenceRuleError):
            rules.deal_damage(state, "missing", 1)


if __name__ == "__main__":
    unittest.main()
