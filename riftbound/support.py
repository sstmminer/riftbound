"""Explicit implementations, never inferred by parsing card text at runtime."""

UNIT_CODES = frozenset(f"OGN-{n:03d}" for n in
                      (1, 3, 10, 11, 12, 13, 15, 27, 28, 30, 39, 49, 51, 52, 55, 65, 66, 82, 88, 131, 142, 148, 159, 171, 175, 176, 210, 211, 215, 217, 219, 222, 223, 232, 234))
SPELL_CODES = frozenset(f"OGN-{n:03d}" for n in (4, 5, 9, 24, 29, 50, 58, 85, 93, 95, 105, 114, 127, 133, 154, 201, 206, 207, 229))
REACTIONS = frozenset({"OGN-058", "OGN-093", "OGN-095", "OGN-127", "OGN-133", "OGN-206", "OGN-207"})
ACCELERATE = frozenset({"OGN-001", "OGN-010", "OGN-030", "OGN-039"})
FIELD_CODES = frozenset({"OGN-276", "OGN-294", "OGN-297"})
LEGEND = "OGN-253"
LEGENDS = frozenset({LEGEND, "OGN-247", "OGN-251"})
RUNES = frozenset({"OGN-007", "OGN-042", "OGN-089", "OGN-126", "OGN-166", "OGN-214"})
TOKEN = "OGN-273"
SUPPORTED = UNIT_CODES | SPELL_CODES | FIELD_CODES | RUNES | LEGENDS | {TOKEN}


def starter_deck() -> dict:
    counts = {1: 3, 10: 3, 11: 1, 12: 3, 13: 3, 15: 2,
              210: 3, 215: 3, 217: 3, 219: 3, 222: 2, 223: 2, 232: 1,
              4: 2, 9: 2, 24: 1, 206: 1, 207: 1, 27: 1}
    main = [f"OGN-{n:03d}" for n, count in counts.items() for _ in range(count)]
    assert len(main) == 40
    return {"legend": LEGEND, "chosen_champion": "OGN-027", "main": main,
            "runes": ["OGN-007"] * 6 + ["OGN-214"] * 6,
            "battlefields": sorted(FIELD_CODES)}


def vision_deck() -> dict:
    codes = (1, 4, 9, 10, 11, 12, 13, 15, 24, 27, 30, 171, 176)
    return {"legend": "OGN-251", "chosen_champion": "OGN-030",
            "main": [f"OGN-{n:03d}" for n in codes for _ in range(3)] + ["OGN-175"],
            "runes": ["OGN-007"] * 6 + ["OGN-166"] * 6,
            "battlefields": sorted(FIELD_CODES)}


def daughter_deck() -> dict:
    """A legal Fury/Mind sample deck for the Daughter of the Void cluster."""
    counts = {1: 3, 3: 3, 4: 3, 9: 3, 10: 3, 11: 2, 12: 3, 13: 3,
              15: 2, 24: 3, 27: 3, 30: 3, 39: 3, 88: 3}
    main = [f"OGN-{n:03d}" for n, count in counts.items() for _ in range(count)]
    assert len(main) == 40
    return {"legend": "OGN-247", "chosen_champion": "OGN-039", "main": main,
            "runes": ["OGN-007"] * 6 + ["OGN-089"] * 6,
            "battlefields": sorted(FIELD_CODES)}
