"""Explicit implementations, never inferred by parsing card text at runtime."""

UNIT_CODES = frozenset(f"OGN-{n:03d}" for n in
                      (1, 10, 11, 12, 13, 15, 27, 210, 215, 217, 219, 222, 223, 232))
SPELL_CODES = frozenset(f"OGN-{n:03d}" for n in (4, 9, 24, 206, 207))
REACTIONS = frozenset({"OGN-206", "OGN-207"})
ACCELERATE = frozenset({"OGN-001", "OGN-010"})
FIELD_CODES = frozenset({"OGN-276", "OGN-294", "OGN-297"})
LEGEND = "OGN-253"
RUNES = frozenset({"OGN-007", "OGN-214"})
TOKEN = "OGN-273"
SUPPORTED = UNIT_CODES | SPELL_CODES | FIELD_CODES | RUNES | {LEGEND, TOKEN}


def starter_deck() -> dict:
    counts = {1: 3, 10: 3, 11: 1, 12: 3, 13: 3, 15: 2,
              210: 3, 215: 3, 217: 3, 219: 3, 222: 2, 223: 2, 232: 1,
              4: 2, 9: 2, 24: 1, 206: 1, 207: 1, 27: 1}
    main = [f"OGN-{n:03d}" for n, count in counts.items() for _ in range(count)]
    assert len(main) == 40
    return {"legend": LEGEND, "chosen_champion": "OGN-027", "main": main,
            "runes": ["OGN-007"] * 6 + ["OGN-214"] * 6,
            "battlefields": sorted(FIELD_CODES)}
