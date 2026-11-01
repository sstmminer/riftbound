"""Catalog-only access to the post-Origins public card snapshot.

The simulator's executable ``OriginsRules`` backend intentionally remains
strict: a card appearing here is not silently playable until its ability has a
registered implementation and regression coverage.  This module gives deck
builders, GUI card browsers, asset tooling, and future set adapters a stable
catalog API without weakening that rule.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .core import Card


def _paths() -> tuple[Path, Path]:
    directory = Path(__file__).with_name("data")
    return directory / "expansions.json", directory / "expansions-source.json"


def load_expansions(*, set_code: str | None = None) -> tuple[dict, ...]:
    payload_path, source_path = _paths()
    payload = payload_path.read_bytes()
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if hashlib.sha256(payload).hexdigest() != source["snapshot_sha256"]:
        raise ValueError("expansion catalog hash mismatch")
    cards = json.loads(payload)
    if len(cards) != source["count"]:
        raise ValueError("expansion catalog count mismatch")
    ids = [card["id"] for card in cards]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate expansion catalog IDs")
    requested = set_code.upper() if set_code else None
    if requested is not None and requested not in source["sets"]:
        raise ValueError(f"unknown expansion set: {requested}")
    selected = [card for card in cards if requested is None or card["set_code"] == requested]
    if requested is not None and not selected:
        raise ValueError(f"empty expansion set: {requested}")
    return tuple(selected)


def expansion_sets() -> tuple[str, ...]:
    source = json.loads(_paths()[1].read_text(encoding="utf-8"))
    return tuple(source["sets"])


def expansion_card_models(*, set_code: str | None = None) -> dict[str, Card]:
    """Return immutable base models for catalog and deck tooling.

    These models contain printed identity and text only.  They are deliberately
    not accepted by ``OriginsRules`` until an executable set adapter exists.
    """

    models = {}
    for row in load_expansions(set_code=set_code):
        # Rules tokens such as Buff and Stun have no card type in the public
        # gallery.  Keep them in the raw catalog, but do not invent a playable
        # Card kind for deck validation.
        if row["type"] not in {"unit", "gear", "spell", "rune", "legend", "battlefield"}:
            continue
        models[row["id"]] = Card(
            row["id"], row["name"], row["type"], frozenset(row["domains"]),
            frozenset(row["tags"]), row["champion"], row["signature"],
            row["unique"], rules_text=row["text"],
        )
    return models


def find_expansion_card(card_id: str) -> dict | None:
    return next((card for card in load_expansions() if card["id"] == card_id), None)
