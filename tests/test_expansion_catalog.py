import unittest

from riftbound.expansion_catalog import (
    expansion_card_models,
    expansion_sets,
    find_expansion_card,
    load_expansions,
)


class ExpansionCatalogTests(unittest.TestCase):
    def test_pinned_sets_and_counts(self):
        self.assertEqual(expansion_sets(), ("OGS", "SFD", "UNL", "VEN", "RAD"))
        cards = load_expansions()
        self.assertEqual(len(cards), 1056)
        self.assertTrue(all(card["image_url"] and card["local_image_path"] for card in cards))
        self.assertEqual(
            {code: len(load_expansions(set_code=code)) for code in expansion_sets()},
            {"OGS": 24, "SFD": 288, "UNL": 288, "VEN": 237, "RAD": 219},
        )

    def test_alternate_prints_have_stable_ids(self):
        star = find_expansion_card("SFD-227-STAR-221")
        self.assertIsNotNone(star)
        self.assertEqual(star["public_code"], "SFD-227*/221")
        self.assertNotEqual(star["id"], "SFD-227-221")
        self.assertEqual(find_expansion_card("SFD-227-221")["name"], "Ahri, Inquisitive")

    def test_models_are_catalog_only_and_preserve_text(self):
        models = expansion_card_models(set_code="UNL")
        self.assertEqual(len(models), 286)
        self.assertEqual(models["UNL-131-219"].kind, "spell")
        self.assertIn("Counter a spell", models["UNL-131-219"].rules_text)


if __name__ == "__main__":
    unittest.main()
