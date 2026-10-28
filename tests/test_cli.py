from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest

from riftbound.cli import main


class CLITests(unittest.TestCase):
    def invoke(self, args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main(args)
        return code, out.getvalue(), err.getvalue()

    def test_status_catalog_and_builtin_deck(self):
        code, out, _ = self.invoke(["status"])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(out)["supported_subset_playable"])
        self.assertFalse(json.loads(out)["full_origins_supported"])
        code, out, _ = self.invoke(["catalog", "--supported"])
        cards = [json.loads(line) for line in out.splitlines()]
        self.assertEqual(len(cards), 210)
        self.assertTrue(all(card["supported"] for card in cards))
        code, out, _ = self.invoke(["deck"])
        self.assertEqual(len(json.loads(out)["main"]), 40)
        code, out, _ = self.invoke(["deck", "--variant", "vision"])
        vision = json.loads(out)
        self.assertEqual(vision["legend"], "OGN-251")
        self.assertIn("OGN-171", vision["main"])
        code, out, _ = self.invoke(["deck", "--variant", "daughter"])
        daughter = json.loads(out)
        self.assertEqual(daughter["legend"], "OGN-247")
        self.assertEqual(len(daughter["main"]), 40)
        code, out, _ = self.invoke(["deck", "--variant", "complex"])
        complex_deck = json.loads(out)
        self.assertEqual(complex_deck["legend"], "OGN-247")
        self.assertEqual(len(complex_deck["main"]), 40)
        self.assertIn("OGN-105", complex_deck["main"])

    def test_gui_module_is_importable_without_opening_a_window(self):
        from riftbound.gui import OriginsGUI
        self.assertTrue(callable(OriginsGUI))

    def test_supported_card_images_are_bundled(self):
        from riftbound.support import LEGENDS, RUNES, SUPPORTED, UNIT_CODES
        root = Path(__file__).parents[1] / "riftbound" / "data" / "images"
        self.assertTrue((root / "card-back.png").is_file())
        for code in SUPPORTED:
            self.assertTrue((root / "OGN" / f"{code}.png").is_file(), code)
        for code in UNIT_CODES | RUNES | LEGENDS:
            self.assertTrue((root / "OGN" / f"{code}-horizontal.png").is_file(), code)

    def test_export_truncation_replay_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/"run"
            code, out, err = self.invoke(["simulate", "--max-steps", "2", "--output", str(output), "--export-decisions"])
            self.assertEqual(code, 0, err)
            summary = json.loads(out)
            self.assertEqual(summary["truncated"], 1)
            self.assertEqual(summary["wins"], [0, 0])
            decisions = [json.loads(line) for line in (output/"decisions-0000.jsonl").read_text().splitlines()]
            self.assertEqual(len(decisions), 2)
            self.assertTrue(all("seed" not in row for row in decisions))
            record = output/"replay-0000.json"
            code, out, err = self.invoke(["replay", str(record)])
            self.assertEqual(code, 0, err)
            self.assertTrue(json.loads(out)["verified"])
            value = json.loads(record.read_text())
            value["audit"]["digests"][1] = "tampered"
            record.write_text(json.dumps(value))
            self.assertEqual(self.invoke(["replay", str(record)])[0], 2)
            self.assertEqual(self.invoke(["simulate", "--output", str(output)])[0], 2)

    def test_validate_deck_and_export_requires_directory(self):
        from riftbound.support import starter_deck
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"deck.json"
            self.assertEqual(self.invoke(["deck", "--output", str(path)])[0], 0)
            self.assertEqual(json.loads(path.read_text()), starter_deck())
            self.assertEqual(self.invoke(["deck", "--output", str(path)])[0], 2)
            self.assertEqual(self.invoke(["validate-deck", str(path)])[0], 0)
        self.assertEqual(self.invoke(["simulate", "--export-decisions"])[0], 2)
