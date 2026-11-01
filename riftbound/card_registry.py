"""Namespaced card implementation registry.

Card text is catalog data; it never becomes executable by being present in the
gallery snapshot.  A set adapter must register an explicit implementation and
its tested hooks.  This keeps future sets out of Origins' code-number branches
until the required timing and target windows are implemented.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class CardImplementation:
    card_id: str
    set_code: str
    kind: str
    status: str = "catalog-only"
    reaction: bool = False
    behavior_id: str | None = None
    static_keywords: frozenset[str] = frozenset()
    entry_effect: str | None = None
    move_effect: str | None = None
    deathknell_effect: str | None = None
    spell_effect: str | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.card_id or not self.set_code:
            raise ValueError("card implementation needs a namespaced ID and set")
        if self.status not in {"catalog-only", "executable"}:
            raise ValueError("unknown implementation status")
        if self.status == "executable" and not any((
                self.behavior_id, self.static_keywords, self.entry_effect,
                self.move_effect, self.deathknell_effect, self.spell_effect)):
            raise ValueError("executable implementation needs an explicit hook")


class CardSetRegistry:
    """Immutable-by-convention registry merged by set adapters."""

    def __init__(self, implementations: Iterable[CardImplementation] = ()) -> None:
        self._items: dict[str, CardImplementation] = {}
        for item in implementations:
            self.register(item)

    def register(self, item: CardImplementation) -> None:
        if item.card_id in self._items:
            raise ValueError(f"card implementation already registered: {item.card_id}")
        self._items[item.card_id] = item

    def merge(self, other: "CardSetRegistry") -> "CardSetRegistry":
        merged = CardSetRegistry(self._items.values())
        for item in other._items.values():
            merged.register(item)
        return merged

    def get(self, card_id: str) -> CardImplementation | None:
        return self._items.get(card_id)

    def is_executable(self, card_id: str) -> bool:
        item = self.get(card_id)
        return item is not None and item.status == "executable"

    def behavior_id(self, card_id: str) -> str:
        item = self.get(card_id)
        return item.behavior_id if item and item.behavior_id else card_id

    def executable_codes(self, *, kind: str | None = None) -> frozenset[str]:
        return frozenset(item.card_id for item in self._items.values()
                         if item.status == "executable"
                         and (kind is None or item.kind == kind))

    def implementations(self) -> tuple[CardImplementation, ...]:
        return tuple(self._items[key] for key in sorted(self._items))


def spiritforged_registry() -> CardSetRegistry:
    """First conservative executable SFD cluster.

    These cards use existing rule primitives or one explicit registered spell
    handler.  More complex Weaponmaster/Equipment, Repeat, Hidden, and nested
    free-play cards remain catalog-only until their shared infrastructure is
    complete; they are never allowed to silently fizzle through a generic path.
    """

    sfd = "SFD"
    return CardSetRegistry([
        CardImplementation("SFD-006-221", sfd, "unit", "executable",
                           entry_effect="enter_ready",
                           notes="I enter ready."),
        CardImplementation("SFD-037-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"deflect"}),
                           notes="Deflect; same keyword predicate as Origins."),
        CardImplementation("SFD-222-221", sfd, "gear", "executable",
                           behavior_id="OGN-040", notes="Seal of Rage resource ability."),
        CardImplementation("SFD-226-221", sfd, "gear", "executable",
                           behavior_id="OGN-081", notes="Seal of Focus resource ability."),
        CardImplementation("SFD-229-221", sfd, "gear", "executable",
                           behavior_id="OGN-120", notes="Seal of Insight resource ability."),
        CardImplementation("SFD-231-221", sfd, "gear", "executable",
                           behavior_id="OGN-163", notes="Seal of Strength resource ability."),
        CardImplementation("SFD-234-221", sfd, "gear", "executable",
                           behavior_id="OGN-204", notes="Seal of Discord resource ability."),
        CardImplementation("SFD-238-221", sfd, "gear", "executable",
                           behavior_id="OGN-245", notes="Seal of Unity resource ability."),
        CardImplementation("SFD-096-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"ganking"}),
                           notes="Ganking."),
        CardImplementation("SFD-156-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"assault_2"}),
                           notes="Assault 2."),
        CardImplementation("SFD-176-221", sfd, "unit", "executable",
                           static_keywords=frozenset({"tank"}),
                           entry_effect="enter_ready_if_base_units",
                           notes="Tank; enters ready with two other units in base."),
        CardImplementation("SFD-087-221", sfd, "spell", "executable",
                           reaction=True, spell_effect="draw_three",
                           notes="Reaction; draw 3."),
        CardImplementation("SFD-036-221", sfd, "unit", "executable",
                           deathknell_effect="draw_if_alone",
                           notes="Deathknell; draw if this unit died alone."),
        CardImplementation("SFD-048-221", sfd, "unit", "executable",
                           move_effect="draw_one",
                           notes="When this unit moves, draw 1."),
        CardImplementation("SFD-094-221", sfd, "unit", "executable",
                           entry_effect="enter_ready_if_dragon",
                           notes="Enters ready if you control another Dragon."),
        CardImplementation("SFD-106-221", sfd, "spell", "executable",
                           reaction=True, spell_effect="draw_mighty",
                           notes="Reaction; draw for each Mighty unit."),
        CardImplementation("SFD-147-221", sfd, "spell", "executable",
                           spell_effect="return_all_units_gear",
                           notes="Return all units and gear to their owners' hands."),
    ])
