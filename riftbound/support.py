"""Explicit implementations, never inferred by parsing card text at runtime."""

UNIT_CODES = frozenset(f"OGN-{n:03d}" for n in
                      (1, 2, 3, 6, 10, 11, 12, 13, 15, 16, 18, 19, 20, 26, 34, 27, 28, 30, 31, 35, 36, 37, 38, 39, 41, 44, 49, 51, 52, 54, 55, 56, 59, 61, 65, 66, 67, 68, 70, 73, 74, 75, 76, 78, 79, 82, 84, 86, 87, 88, 91, 92, 96, 97, 100, 103, 106, 107, 109, 110, 111, 112, 113, 116, 117, 118, 119, 121, 125, 130, 131, 132, 135, 136, 137, 139, 140, 141, 142, 147, 148, 149, 150, 151, 155, 157, 158, 159, 161, 162, 164, 165, 167, 171, 174, 175, 176, 177, 178, 185, 188, 189, 190, 191, 192, 193, 194, 195, 196, 197, 199, 200, 202, 205, 208, 210, 211, 215, 216, 217, 218, 219, 222, 223, 225, 226, 230, 231, 232, 234, 235, 236, 238, 239, 240, 241, 243, 246))
GEAR_CODES = frozenset(f"OGN-{n:03d}" for n in
                       (17, 21, 23, 32, 40, 60, 63, 72, 77, 81, 90, 98, 99, 101, 120, 124, 143, 152, 160, 163, 181, 182, 184, 186, 204, 212, 227, 228, 242, 245))
SPELL_CODES = frozenset(f"OGN-{n:03d}" for n in (4, 5, 8, 9, 14, 22, 24, 25, 29, 33, 43, 45, 46, 47, 48, 50, 53, 57, 58, 62, 64, 69, 71, 80, 83, 85, 93, 94, 95, 102, 104, 105, 108, 114, 115, 122, 123, 127, 128, 129, 133, 134, 138, 144, 145, 146, 153, 154, 156, 168, 169, 170, 172, 173, 179, 180, 183, 187, 198, 201, 203, 206, 207, 209, 213, 220, 221, 224, 229, 233, 237, 244, 248, 250, 252, 254, 256, 258, 260, 262, 264, 266, 268, 270))
REACTIONS = frozenset({"OGN-045", "OGN-064", "OGN-080", "OGN-046", "OGN-048", "OGN-058", "OGN-083", "OGN-093", "OGN-095", "OGN-104", "OGN-127", "OGN-133", "OGN-169", "OGN-206", "OGN-207", "OGN-266"})
HIDDEN_CODES = frozenset({"OGN-053", "OGN-057", "OGN-077", "OGN-083", "OGN-094", "OGN-097", "OGN-121", "OGN-135", "OGN-168", "OGN-197", "OGN-199", "OGN-213", "OGN-220", "OGN-256"})
ACCELERATE = frozenset({"OGN-001", "OGN-010", "OGN-030", "OGN-039", "OGN-150"})
FIELD_CODES = frozenset({"OGN-275", "OGN-276", "OGN-277", "OGN-278", "OGN-279", "OGN-280", "OGN-281", "OGN-282", "OGN-283", "OGN-284", "OGN-285", "OGN-286", "OGN-287", "OGN-288", "OGN-289", "OGN-290", "OGN-291", "OGN-292", "OGN-293", "OGN-294", "OGN-295", "OGN-296", "OGN-297", "OGN-298"})
LEGEND = "OGN-253"
LEGENDS = frozenset({LEGEND, "OGN-247", "OGN-249", "OGN-251", "OGN-255", "OGN-257", "OGN-259", "OGN-261", "OGN-263", "OGN-265", "OGN-267", "OGN-269"})
RUNES = frozenset({"OGN-007", "OGN-042", "OGN-089", "OGN-126", "OGN-166", "OGN-214"})
TOKEN = "OGN-273"
SPRITE_TOKEN = "OGN-274"
TOKEN_CODES = frozenset({"OGN-271", "OGN-272", "OGN-273", "OGN-274"})
SUPPORTED = UNIT_CODES | GEAR_CODES | SPELL_CODES | FIELD_CODES | RUNES | LEGENDS | TOKEN_CODES
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


def _mechanics_deck(counts: dict[int, int], *, legend="OGN-247", champion="OGN-039", runes=("OGN-007", "OGN-126")) -> dict:
    """Build a legal 40-card QA deck from explicit supported card numbers."""
    main = [f"OGN-{number:03d}" for number, count in counts.items() for _ in range(count)]
    assert len(main) == 40
    if champion not in main:
        main[-1] = champion
    return {"legend": legend, "chosen_champion": champion, "main": main,
            "runes": [runes[0]] * 6 + [runes[1]] * 6,
            "battlefields": list(DEFAULT_FIELDS)}


def repeat_targets_deck() -> dict:
    """QA deck for Icathian Rain, Falling Star and explicit target confirmation."""
    return _mechanics_deck({248: 3, 29: 3, 105: 3, 3: 3, 8: 3,
                            1: 3, 10: 3, 12: 3, 13: 3, 15: 3,
                            30: 3, 39: 3, 11: 3, 16: 1},
                           legend="OGN-247", champion="OGN-039",
                           runes=("OGN-007", "OGN-089"))


def replay_windows_deck() -> dict:
    """QA deck for trash replay and player choice windows."""
    return _mechanics_deck({196: 3, 187: 3, 183: 3, 201: 3, 198: 3,
                            29: 3, 8: 3, 9: 3, 5: 3, 22: 3,
                            24: 3, 1: 3, 10: 2, 30: 2},
                           legend="OGN-251", champion="OGN-030",
                           runes=("OGN-007", "OGN-166"))


def cost_abilities_deck() -> dict:
    """QA deck for additional costs, Accelerate, Assault and Udyr."""
    return _mechanics_deck({2: 3, 20: 3, 34: 3, 150: 3, 157: 3,
                            1: 3, 3: 3, 10: 3, 12: 3, 13: 3,
                            15: 3, 4: 3, 9: 3, 217: 1},
                           legend="OGN-249", champion="OGN-158",
                           runes=("OGN-007", "OGN-126"))


def resource_and_gear_deck() -> dict:
    """QA deck for Malzahar, Gear sacrifice and Order replay effects."""
    return _mechanics_deck({113: 3, 226: 3, 231: 3, 227: 3, 237: 3,
                            109: 3, 110: 3, 116: 3, 117: 3, 118: 3,
                            119: 3, 234: 3, 238: 3, 232: 1},
                           legend="OGN-265", champion="OGN-117",
                           runes=("OGN-089", "OGN-214"))


def reveal_targets_deck() -> dict:
    """QA deck for public reveal, Hidden placement and target windows."""
    return _mechanics_deck({264: 3, 183: 3, 196: 3, 187: 3, 201: 3,
                            198: 3, 189: 3, 190: 3, 197: 3, 202: 3,
                            205: 3, 109: 3, 110: 3, 119: 1},
                           legend="OGN-263", champion="OGN-197",
                           runes=("OGN-089", "OGN-166"))
