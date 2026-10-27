"""Validate card image mappings against the packaged artwork files.

This is intentionally independent of the game engine.  It can be run after
adding a card to the executable pool to catch an incomplete asset bundle.
"""
import argparse
import json
from pathlib import Path


def inspect_assets(data_dir: Path, require_horizontal: bool = False) -> dict:
    manifest = json.loads((data_dir / "card_images.json").read_text(encoding="utf-8"))
    cards = manifest.get("cards", {})
    missing = []
    missing_horizontal = []
    for code, relative in cards.items():
        if not (data_dir / relative).is_file():
            missing.append(code)
        horizontal = data_dir / Path(relative).parent / (Path(relative).stem + "-horizontal.png")
        if not horizontal.is_file():
            missing_horizontal.append(code)
    result = {
        "mapped": len(cards),
        "missing": sorted(missing),
        "missing_horizontal": sorted(missing_horizontal),
    }
    if require_horizontal and missing_horizontal:
        result["ok"] = False
    else:
        result["ok"] = not missing
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("riftbound/data"))
    parser.add_argument("--require-horizontal", action="store_true")
    args = parser.parse_args()
    result = inspect_assets(args.data_dir, args.require_horizontal)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
