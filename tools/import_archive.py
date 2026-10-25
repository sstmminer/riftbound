"""Normalize a pinned official-source archive without executing its scripts."""
import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, default=Path("riftbound/data"))
    args = parser.parse_args()
    raw_bytes = (args.archive / "data/cards.json").read_bytes()
    errata_bytes = (args.archive / "data/errata.json").read_bytes()
    rows = json.loads(raw_bytes)
    by_id = {row["official_card_id"]: row for row in rows}
    normalized = []
    for number in range(1, 299):
        key = f"ogn-{number:03d}-298"
        row = by_id[key]
        raw = json.loads(row["raw_record"])
        supertypes = [item["id"] for item in raw["cardType"].get("superType", [])]
        normalized.append({
            "code": f"OGN-{number:03d}", "official_id": key, "name": row["name"],
            "type": json.loads(row["card_type"])[0].lower(),
            "domains": [d.lower() for d in json.loads(row["domains"] or "[]") if d != "Colorless"],
            "tags": json.loads(row["tags"] or "[]"),
            "champion": "champion" in supertypes, "signature": "signature" in supertypes,
            "token": number in (271, 272, 273, 274),
            "energy": int(row["cost"]) if row["cost"] is not None else None,
            "power_cost": int(row["power_cost"] or 0),
            "might": int(row["power"]) if "Unit" in row["card_type"] and row["power"] is not None else None,
            "text": row["effective_rules_text"] or row["printed_rules_text"] or "",
            "printed_text": row["printed_rules_text"] or "",
            "errata_status": row["errata_status"], "source_url": row["source_url"],
        })
    args.output.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(normalized, ensure_ascii=False, indent=2) + "\n").encode()
    (args.output / "origins.json").write_bytes(payload)
    metadata = {
        "source": "https://github.com/sstmminer/riftbound/tree/a330ca8325ae792548660b1ccef0e7dd97062bd7",
        "commit": "a330ca8325ae792548660b1ccef0e7dd97062bd7",
        "cards_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "errata_sha256": hashlib.sha256(errata_bytes).hexdigest(),
        "snapshot_sha256": hashlib.sha256(payload).hexdigest(), "count": 298,
        "selection": "ogn-001-298 through ogn-298-298; distinct base print IDs",
        "text_policy": "Known revised text first, otherwise gallery snapshot; retain incomplete errata status.",
        "cost_mapping": "cost=energy, power_cost=domain power, power=Might; null energy is not zero.",
        "limitations": ["Official gallery metadata gap of 8 records is unresolved.",
                        "Unmatched LeBlanc errata belongs to Unleashed announcement.",
                        "Card data and artwork rights belong to Riot Games.",
                        "Only the explicit supported subset is executable."],
    }
    (args.output / "origins-source.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Imported {len(normalized)} Origins base records")


if __name__ == "__main__":
    main()
