"""Read-only Origins card snapshot. Text presence does not imply engine support."""

import hashlib
import json
from pathlib import Path

from .engine import RulesUnavailable
from .support import SUPPORTED


def load_origins() -> tuple[dict, ...]:
    directory = Path(__file__).with_name("data")
    payload = (directory / "origins.json").read_bytes()
    provenance = json.loads((directory / "origins-source.json").read_text())
    if hashlib.sha256(payload).hexdigest() != provenance["snapshot_sha256"]:
        raise ValueError("Origins catalog hash mismatch")
    cards = json.loads(payload)
    expected = {f"OGN-{i:03d}" for i in range(1, 299)}
    if len(cards) != 298 or {c["code"] for c in cards} != expected:
        raise ValueError("incomplete or duplicate Origins base catalog")
    if len({c["name"] for c in cards}) != 298:
        raise ValueError("duplicate canonical card names")
    return tuple(cards)


def require_supported(card_codes: tuple[str, ...]) -> None:
    """Reject mechanics outside the explicit, tested executable subset."""
    known = {card["code"] for card in load_origins()}
    unknown = set(card_codes) - known
    if unknown:
        raise ValueError(f"unknown Origins cards: {sorted(unknown)}")
    unsupported = set(card_codes) - SUPPORTED
    if unsupported:
        raise RulesUnavailable(f"Unsupported Origins cards: {sorted(unsupported)}")
