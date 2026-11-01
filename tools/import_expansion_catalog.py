"""Normalize the pinned public card-gallery snapshot for sets after Origins.

The executable Origins backend deliberately remains separate from this catalog.
This importer records every public print in the selected sets, including promo
and alternate-print IDs, without claiming that their abilities are implemented.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SETS = ("OGS", "SFD", "UNL", "VEN", "RAD")


def _git_bytes(ref: str, path: str) -> bytes:
    return subprocess.run(
        ["git", "show", f"{ref}:{path}"], cwd=ROOT, check=True,
        stdout=subprocess.PIPE,
    ).stdout


def _read_bytes(archive_root: Path | None, ref: str, path: str) -> bytes:
    if archive_root is not None:
        return (archive_root / path).read_bytes()
    return _git_bytes(ref, path)


def _json_list(value):
    if value in (None, "", []):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return value


def _number(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    if isinstance(value, dict):
        nested = value.get("value")
        if isinstance(nested, dict):
            nested = nested.get("label")
        if isinstance(nested, (int, str)) and str(nested).strip().isdigit():
            return int(str(nested).strip())
    return None


def _stable_id(row: dict) -> str:
    """Turn an official print ID into a collision-free deck/catalog ID."""

    return re.sub(r"[^A-Z0-9]+", "-", row["official_card_id"].upper()).strip("-")


def normalize(rows: list[dict], selected: tuple[str, ...]) -> list[dict]:
    selected_set = set(selected)
    result = []
    for row in rows:
        if row.get("set_code") not in selected_set:
            continue
        raw = json.loads(row["raw_record"])
        card_types = _json_list(row.get("card_type"))
        supertypes = [item.get("id", "").lower() for item in raw.get("cardType", {}).get("superType", [])]
        kind = str(card_types[0] if card_types else "").lower()
        domains = [str(domain).lower() for domain in _json_list(row.get("domains"))
                   if str(domain).lower() != "colorless"]
        tags = _json_list(row.get("tags"))
        result.append({
            "id": _stable_id(row),
            "official_id": row["official_card_id"],
            "public_code": row.get("public_code"),
            "set_code": row["set_code"],
            "set_name": row["set_name"],
            "collector_number": row["collector_number"],
            "name": row["name"],
            "type": kind,
            "domains": domains,
            "tags": tags,
            "champion": "champion" in supertypes,
            "signature": "signature" in supertypes,
            "token": "token" in supertypes,
            "unique": "unique" in supertypes,
            "energy": _number(row.get("cost")),
            "power_cost": _number(row.get("power")),
            "might": _number(row.get("power")) if kind == "unit" else None,
            "text": row.get("effective_rules_text") or row.get("printed_rules_text") or "",
            "printed_text": row.get("printed_rules_text") or "",
            "errata_status": row.get("errata_status"),
            "image_url": row.get("image_url"),
            "local_image_path": row.get("local_image_path"),
            "source_url": row.get("source_url"),
        })
    result.sort(key=lambda item: (item["set_code"], item["official_id"]))
    ids = [item["id"] for item in result]
    if len(ids) != len(set(ids)):
        raise ValueError("normalized expansion IDs are not unique")
    return result


def import_catalog(*, archive_root: Path | None, ref: str,
                   output: Path, source_output: Path, selected: tuple[str, ...]) -> None:
    cards_bytes = _read_bytes(archive_root, ref, "data/cards.json")
    errata_bytes = _read_bytes(archive_root, ref, "data/errata.json")
    coverage_bytes = _read_bytes(archive_root, ref, "data/coverage.json")
    rows = json.loads(cards_bytes)
    cards = normalize(rows, selected)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(cards, ensure_ascii=False, indent=2) + "\n").encode()
    output.write_bytes(payload)
    counts = Counter(card["set_code"] for card in cards)
    source = {
        "source": "https://github.com/sstmminer/riftbound/tree/archive-download",
        "source_ref": ref,
        "cards_sha256": hashlib.sha256(cards_bytes).hexdigest(),
        "errata_sha256": hashlib.sha256(errata_bytes).hexdigest(),
        "coverage_sha256": hashlib.sha256(coverage_bytes).hexdigest(),
        "snapshot_sha256": hashlib.sha256(payload).hexdigest(),
        "sets": list(selected),
        "counts": dict(sorted(counts.items())),
        "count": len(cards),
        "selection": "all public print records in the selected set codes, including alternate and promo prints",
        "text_policy": "effective_rules_text when present, otherwise printed_rules_text; preserve errata status",
        "image_policy": "record official image_url and archive local_image_path; assets are fetched lazily by the expansion asset tool",
        "execution_policy": "catalog-only until a card has an explicit, tested Rules implementation; no text parsing fallback",
    }
    source_output.parent.mkdir(parents=True, exist_ok=True)
    source_output.write_text(json.dumps(source, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Imported {len(cards)} expansion records: {dict(sorted(counts.items()))}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git-ref", default="origin/archive-download")
    parser.add_argument("--archive-root", type=Path)
    parser.add_argument("--sets", nargs="+", default=list(DEFAULT_SETS))
    parser.add_argument("--output", type=Path, default=ROOT / "riftbound/data/expansions.json")
    parser.add_argument("--source-output", type=Path, default=ROOT / "riftbound/data/expansions-source.json")
    args = parser.parse_args()
    selected = tuple(dict.fromkeys(s.upper() for s in args.sets))
    import_catalog(archive_root=args.archive_root, ref=args.git_ref,
                   output=args.output, source_output=args.source_output, selected=selected)


if __name__ == "__main__":
    main()
