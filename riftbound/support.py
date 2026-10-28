"""Explicit implementations, never inferred by parsing card text at runtime."""

UNIT_CODES = frozenset(f"OGN-{n:03d}" for n in
                      (1, 3, 10, 11, 12, 13, 15, 16, 27, 28, 30, 35, 37, 39, 49, 51, 52, 54, 55, 61, 65, 66, 74, 78, 79, 82, 84, 86, 87, 88, 92, 96, 97, 100, 103, 106, 116, 118, 119, 125, 130, 131, 132, 136, 137, 139, 142, 148, 151, 159, 161, 164, 165, 171, 174, 175, 176, 185, 188, 191, 195, 197, 210, 211, 215, 216, 217, 218, 219, 222, 223, 225, 232, 234, 238, 239, 240, 241, 243, 246))
SPELL_CODES = frozenset(f"OGN-{n:03d}" for n in (4, 5, 9, 14, 24, 29, 43, 46, 47, 48, 50, 53, 58, 69, 83, 85, 93, 94, 95, 104, 105, 114, 123, 127, 128, 129, 133, 134, 138, 146, 154, 169, 170, 172, 173, 201, 206, 207, 209, 213, 220, 229, 233, 252, 260, 262, 266, 270))
REACTIONS = frozenset({"OGN-046", "OGN-048", "OGN-058", "OGN-083", "OGN-093", "OGN-095", "OGN-104", "OGN-127", "OGN-133", "OGN-169", "OGN-206", "OGN-207", "OGN-266"})
ACCELERATE = frozenset({"OGN-001", "OGN-010", "OGN-030", "OGN-039"})
FIELD_CODES = frozenset({"OGN-275", "OGN-276", "OGN-277", "OGN-280", "OGN-281", "OGN-282", "OGN-283", "OGN-284", "OGN-285", "OGN-286", "OGN-287", "OGN-288", "OGN-289", "OGN-290", "OGN-291", "OGN-292", "OGN-293", "OGN-294", "OGN-295", "OGN-296", "OGN-297", "OGN-298"})
LEGEND = "OGN-253"
LEGENDS = frozenset({LEGEND, "OGN-247", "OGN-249", "OGN-251", "OGN-255", "OGN-257", "OGN-259", "OGN-261", "OGN-265", "OGN-267", "OGN-269"})
RUNES = frozenset({"OGN-007", "OGN-042", "OGN-089", "OGN-126", "OGN-166", "OGN-214"})
TOKEN = "OGN-273"
SUPPORTED = UNIT_CODES | SPELL_CODES | FIELD_CODES | RUNES | LEGENDS | {TOKEN}
DEFAULT_FIELDS = ("OGN-276", "OGN-294", "OGN-297")


def starter_deck() -> dict:
    counts = {1: 3, 10: 3, 11: 1, 12: 3, 13: 3, 15: 2,
              210: 3, 215: 3, 217: 3, 219: 3, 222: 2, 223: 2, 232: 1,
              4: 2, 9: 2, 24: 1, 206: 1, 207: 1, 27: 1}
    main = [f"OGN-{n:03d}" for n, count in counts.items() for _ in range(count)]
    assert len(main) == 40
    return {"legend": LEGEND, "chosen_champion": "OGN-027", "main": main,
            "runes": ["OGN-007"] * 6 + ["OGN-214"] * 6,
            "battlefields": list(DEFAULT_FIELDS)}


def vision_deck() -> dict:
    codes = (1, 4, 9, 10, 11, 12, 13, 15, 24, 27, 30, 171, 176)
    return {"legend": "OGN-251", "chosen_champion": "OGN-030",
            "main": [f"OGN-{n:03d}" for n in codes for _ in range(3)] + ["OGN-175"],
            "runes": ["OGN-007"] * 6 + ["OGN-166"] * 6,
            "battlefields": list(DEFAULT_FIELDS)}


def daughter_deck() -> dict:
    """A legal Fury/Mind sample deck for the Daughter of the Void cluster."""
    counts = {1: 3, 3: 3, 4: 3, 9: 3, 10: 3, 11: 2, 12: 3, 13: 3,
              15: 2, 24: 3, 27: 3, 30: 3, 39: 3, 88: 3}
    main = [f"OGN-{n:03d}" for n, count in counts.items() for _ in range(count)]
    assert len(main) == 40
    return {"legend": "OGN-247", "chosen_champion": "OGN-039", "main": main,
            "runes": ["OGN-007"] * 6 + ["OGN-089"] * 6,
            "battlefields": list(DEFAULT_FIELDS)}


def complex_test_deck() -> dict:
    """A legal Fury/Mind sandbox for exercising the implemented windows.

    The list intentionally concentrates the currently executable mechanics:
    optional Legion buffs, Vision, Deathknell, temporary Might, Assault,
    reactions, movement and the explicit multi-target Singularity path.
    It is a deterministic QA fixture, not a competitive list.
    """
    counts = {
        1: 2, 3: 3, 10: 2, 13: 2, 16: 3, 39: 3,
        86: 3, 87: 2, 88: 3, 96: 3, 103: 3, 119: 3,
        24: 2, 93: 2, 104: 2, 105: 2,
    }
    main = [f"OGN-{n:03d}" for n, count in counts.items() for _ in range(count)]
    assert len(main) == 40
    return {"legend": "OGN-247", "chosen_champion": "OGN-039", "main": main,
            "runes": ["OGN-007"] * 6 + ["OGN-089"] * 6,
            "battlefields": ["OGN-281", "OGN-285", "OGN-288"]}
