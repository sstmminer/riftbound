"""Declarative registry for card abilities.

The Origins rules engine keeps card text out of the runtime parser.  This
registry is the corresponding source of truth for *activated* abilities: each
entry declares its source card, whether activating it requires exhausting the
source, how targets are selected, and which explicit action handler resolves
it.  Consumers such as Heimerdinger query this table instead of maintaining a
card-code whitelist.

The registry intentionally contains a small number of non-exhausted abilities
as well.  They are useful metadata for the ordinary rules engine, but
``copyable_for_heimer`` excludes them by construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping


SourceKind = str  # ``unit``, ``legend`` or ``gear``


@dataclass(frozen=True)
class AbilitySpec:
    """Rule metadata for one named ability.

    ``action_kind`` is the explicit backend action that performs the ability;
    it is deliberately an identifier rather than a callable so the registry is
    serializable, inspectable, and safe to expose to a GUI or future backend.
    ``self_reference`` describes pronouns such as Gear's "kill this" and lets
    a copied ability resolve against the activating source instead of guessing
    from the original card.
    """

    ability_id: str
    source_kind: SourceKind
    source_codes: frozenset[str]
    requires_exhaust: bool
    action_kind: str
    target_mode: str = "none"
    timing: str = "main"
    copyable_by_heimer: bool | None = None
    self_reference: str = "activating_source"
    cost: Mapping[str, object] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.ability_id or not isinstance(self.ability_id, str):
            raise ValueError("ability_id must be a non-empty string")
        if self.source_kind not in {"unit", "legend", "gear"}:
            raise ValueError(f"invalid ability source kind: {self.source_kind}")
        if not self.source_codes or not all(isinstance(code, str) for code in self.source_codes):
            raise ValueError(f"ability {self.ability_id} needs source card codes")
        if not self.action_kind:
            raise ValueError(f"ability {self.ability_id} needs an action handler")
        if self.copyable_by_heimer is None:
            object.__setattr__(self, "copyable_by_heimer", self.requires_exhaust)
        if self.copyable_by_heimer and not self.requires_exhaust:
            raise ValueError(
                f"ability {self.ability_id} cannot be copied by Heimer without exhaust cost"
            )

    @property
    def copyable(self) -> bool:
        """Whether Heimer can acquire this ability under its printed rule."""

        return bool(self.requires_exhaust and self.copyable_by_heimer)

    def matches(self, source_kind: SourceKind, card_code: str) -> bool:
        return self.source_kind == source_kind and card_code in self.source_codes


class AbilityRegistry:
    """Validated, deterministic registry of explicit ability metadata."""

    def __init__(self, specs: Iterable[AbilitySpec] = ()) -> None:
        self._specs: dict[str, AbilitySpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: AbilitySpec) -> AbilitySpec:
        if not isinstance(spec, AbilitySpec):
            raise TypeError("ability registry accepts AbilitySpec values")
        if spec.ability_id in self._specs:
            raise ValueError(f"ability already registered: {spec.ability_id}")
        self._specs[spec.ability_id] = spec
        return spec

    def get(self, ability_id: str) -> AbilitySpec:
        try:
            return self._specs[ability_id]
        except KeyError as exc:
            raise KeyError(f"unregistered ability: {ability_id}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def all(self) -> tuple[AbilitySpec, ...]:
        return tuple(self._specs[name] for name in self.names())

    def for_source(self, source_kind: SourceKind, card_code: str,
                   *, requires_exhaust: bool | None = None,
                   copyable_by_heimer: bool | None = None) -> tuple[AbilitySpec, ...]:
        values = [spec for spec in self._specs.values()
                  if spec.matches(source_kind, card_code)]
        if requires_exhaust is not None:
            values = [spec for spec in values if spec.requires_exhaust == requires_exhaust]
        if copyable_by_heimer is not None:
            values = [spec for spec in values if spec.copyable == copyable_by_heimer]
        return tuple(sorted(values, key=lambda spec: spec.ability_id))

    def copyable_for_heimer(self, source_kind: SourceKind, card_code: str) -> tuple[AbilitySpec, ...]:
        """Return exactly the exhaust abilities Heimer may copy.

        The `requires_exhaust` filter is repeated here intentionally.  It is a
        rules invariant rather than an incidental property of today's card
        registrations, so a future registration cannot accidentally broaden
        Heimer's scope by setting only `copyable_by_heimer=True`.
        """

        return self.for_source(source_kind, card_code,
                               requires_exhaust=True, copyable_by_heimer=True)

    def as_dict(self) -> list[dict[str, object]]:
        return [{
            "ability_id": spec.ability_id,
            "source_kind": spec.source_kind,
            "source_codes": sorted(spec.source_codes),
            "requires_exhaust": spec.requires_exhaust,
            "copyable_by_heimer": spec.copyable,
            "action_kind": spec.action_kind,
            "target_mode": spec.target_mode,
            "timing": spec.timing,
            "self_reference": spec.self_reference,
            "cost": dict(spec.cost),
            "notes": spec.notes,
        } for spec in self.all()]


def _spec(ability_id: str, source_kind: SourceKind, codes: Iterable[str],
          action_kind: str, *, target_mode: str = "none", timing: str = "main",
          requires_exhaust: bool = True, copyable_by_heimer: bool | None = None,
          self_reference: str = "activating_source", cost: Mapping[str, object] | None = None,
          notes: str = "") -> AbilitySpec:
    return AbilitySpec(
        ability_id=ability_id, source_kind=source_kind,
        source_codes=frozenset(codes), requires_exhaust=requires_exhaust,
        action_kind=action_kind, target_mode=target_mode, timing=timing,
        copyable_by_heimer=copyable_by_heimer, self_reference=self_reference,
        cost={} if cost is None else dict(cost), notes=notes,
    )


def origins_ability_registry() -> AbilityRegistry:
    """Build the declarative Origins ability table.

    Every currently known Origins `[E]` ability is represented here.  The
    source code is deliberately separate from `action_kind`, allowing a
    copied ability to use the same resolver with a different activating source
    (for example Heimerdinger).  Non-exhausted examples are registered as
    non-copyable to make the boundary explicit and testable.
    """

    specs: list[AbilitySpec] = []

    # Unit abilities.  Vi and Udyr are deliberately registered as ordinary
    # non-exhausted abilities: Heimer must not copy them merely because an old
    # implementation happened to expose their actions beside E abilities.
    specs.extend([
        _spec("unit.caitlyn_damage", "unit", ["OGN-068"], "unit_caitlyn",
               target_mode="unit_at_battlefield", notes="Damage equal to source Might."),
        _spec("unit.lee_sin_buff", "unit", ["OGN-078"], "unit_buff",
               notes="Give the activating unit a Buff."),
        _spec("unit.malzahar_rainbow", "unit", ["OGN-113"], "unit_malzahar",
               target_mode="friendly_unit_or_gear", timing="action",
               cost={"discard_or_kill": True, "power": ["any", "any"]}),
        _spec("unit.vi_recycle_buff", "unit", ["OGN-036"], "unit_recycle_buff",
               requires_exhaust=False, copyable_by_heimer=False,
               timing="main", target_mode="none",
               notes="Vi's printed ability recycles a card but does not exhaust."),
        _spec("unit.udyr_choice", "unit", ["OGN-157"], "unit_udyr",
               requires_exhaust=False, copyable_by_heimer=False,
               target_mode="choice", notes="Spend a Buff; no exhaust symbol."),
    ])

    # Legend abilities.  Resource reactions remain copyable because the card
    # explicitly requires E before producing their resource.
    specs.extend([
        _spec("legend.daughter_spell_power", "legend", ["OGN-247"], "legend_spell_power",
               timing="reaction", target_mode="none", cost={"resource": "spell_any"}),
        _spec("legend.relentless_channel", "legend", ["OGN-249"], "legend_channel",
               target_mode="none", cost={"rune": "exhausted"}),
        _spec("legend.hand_of_noxus_energy", "legend", ["OGN-253"], "legend_energy",
               timing="reaction", cost={"energy": 1}, notes="Legion condition remains in resolver."),
        _spec("legend.blind_monk_buff", "legend", ["OGN-257"], "legend_buff",
               target_mode="friendly_unit", cost={"energy": 1}),
        _spec("legend.unforgiven_move", "legend", ["OGN-259"], "legend_move",
               target_mode="friendly_unit_destination", cost={"energy": 2}),
        _spec("legend.swift_scout_teemo", "legend", ["OGN-263"], "legend_teemo",
               target_mode="teemo_in_champion_or_board", cost={"energy": 1}),
        _spec("legend.herald_recruit", "legend", ["OGN-265"], "legend_recruit",
               target_mode="none", cost={"energy": 1}),
        _spec("legend.bounty_hunter_ganking", "legend", ["OGN-267"], "legend_ganking",
               target_mode="friendly_unit"),
    ])

    # Gear abilities.  The registry captures every E ability from the current
    # Origins catalog, including ones whose resolver is still specialized.
    specs.extend([
        _spec("gear.iron_ballista_damage", "gear", ["OGN-017"], "gear_damage",
               target_mode="unit_at_battlefield"),
        _spec("gear.sun_disc_ready", "gear", ["OGN-021"], "gear_ready_next",
               target_mode="none"),
        _spec("gear.unlicensed_armory_protect", "gear", ["OGN-023"], "gear_armory_protect",
               target_mode="friendly_unit", cost={"discard": 1}),
        _spec("gear.ravenborn_tome_bonus", "gear", ["OGN-032"], "gear_tome",
               target_mode="none"),
        _spec("gear.seal_of_rage_resource", "gear", ["OGN-040"], "gear_resource",
               timing="reaction", cost={"resource": "fury"}),
        _spec("gear.seal_of_focus_resource", "gear", ["OGN-081"], "gear_resource",
               timing="reaction", cost={"resource": "calm"}),
        _spec("gear.orb_of_regret_debuff", "gear", ["OGN-090"], "gear_debuff",
               target_mode="unit"),
        _spec("gear.energy_conduit_resource", "gear", ["OGN-098"], "gear_resource",
               timing="reaction", cost={"energy": 1}),
        _spec("gear.garbage_grabber", "gear", ["OGN-099"], "gear_grab",
               target_mode="none", cost={"energy": 1, "recycle": 3}),
        _spec("gear.arena_bar_buff", "gear", ["OGN-124"], "gear_buff_exhausted",
               target_mode="friendly_exhausted_unit"),
        _spec("gear.seal_of_insight_resource", "gear", ["OGN-120"], "gear_resource",
               timing="reaction", cost={"resource": "mind"}),
        _spec("gear.seal_of_strength_resource", "gear", ["OGN-163"], "gear_resource",
               timing="reaction", cost={"resource": "body"}),
        _spec("gear.pack_of_wonders_return", "gear", ["OGN-181"], "gear_return",
               target_mode="friendly_gear_unit_hidden"),
        _spec("gear.syren_move", "gear", ["OGN-184"], "gear_move",
               target_mode="friendly_unit_at_battlefield", cost={"energy": 1}),
        _spec("gear.treasure_trove_kill", "gear", ["OGN-186"], "gear_kill",
               target_mode="none", self_reference="activating_source"),
        _spec("gear.seal_of_discord_resource", "gear", ["OGN-204"], "gear_resource",
               timing="reaction", cost={"resource": "chaos"}),
        _spec("gear.baited_hook", "gear", ["OGN-242"], "gear_baited_hook",
               target_mode="friendly_unit", cost={"energy": 1, "power": "order"}),
        _spec("gear.seal_of_unity_resource", "gear", ["OGN-245"], "gear_resource",
               timing="reaction", cost={"resource": "order"}),
    ])

    # Explicit non-E examples.  Keeping them in the same table makes the
    # exclusion visible to tools and prevents future code from inferring
    # copyability from the existence of an action handler.
    specs.extend([
        _spec("unit.nocturne_ganking", "unit", ["OGN-194"], "unit_static_ganking",
               requires_exhaust=False, copyable_by_heimer=False, timing="static"),
        _spec("gear.zhonya_death_replacement", "gear", ["OGN-077"], "gear_death_replacement",
               requires_exhaust=False, copyable_by_heimer=False, timing="replacement"),
    ])
    return AbilityRegistry(specs)


ORIGINS_ABILITIES = origins_ability_registry()
