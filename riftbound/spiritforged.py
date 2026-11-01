"""Spiritforged adapter for the first executable expansion cluster.

This adapter composes the audited Origins timing engine with the namespaced SFD
card registry.  Unregistered SFD cards remain explicit ``RulesUnavailable``
instead of entering a generic path with silently missing text.
"""

from __future__ import annotations

from .expansion_catalog import load_expansions
from .origins import OriginsRules
from .card_registry import spiritforged_registry


class SpiritforgedRules(OriginsRules):
    """Origins core plus the currently executable Spiritforged cluster."""

    def __init__(self, decks=None, *, extra_fields=()):
        registry = spiritforged_registry()
        # Load the complete SFD namespace so unsupported cards fail with the
        # explicit RulesUnavailable gate rather than an opaque unknown-ID
        # error.  Only registry entries marked executable may enter actions.
        rows = load_expansions(set_code="SFD")
        super().__init__(decks, extra_fields=extra_fields,
                         card_registry=registry, additional_cards=rows)
