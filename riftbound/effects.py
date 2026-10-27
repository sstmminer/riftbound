"""Small, backend-neutral registry for explicit card effect handlers.

Card text is deliberately not interpreted at runtime.  A rules backend registers
the effect names it knows how to resolve and dispatches chain items through this
registry.  This keeps the timing/chain code independent from the growing set of
card-specific handlers and makes an unsupported effect fail loudly.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class UnknownEffectError(ValueError):
    """Raised when a chain item has no explicit implementation."""


EffectHandler = Callable[[dict, dict, Any], bool]


@dataclass(frozen=True)
class EffectRegistration:
    """Public metadata for one registered effect."""

    name: str
    handler: EffectHandler


class EffectRegistry:
    """Explicit name-to-handler dispatch table.

    Handlers receive ``(state, item, rng)`` and return ``True`` when the chain
    item completed.  Returning ``False`` means the handler opened a pending
    decision window and the caller must leave the chain paused.  The registry
    does not inspect card text or provide fallback behavior.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, EffectRegistration] = {}

    def register(self, name: str, handler: EffectHandler | None = None):
        """Register a handler, or return a decorator when ``handler`` is omitted."""

        if not isinstance(name, str) or not name:
            raise ValueError("effect name must be a non-empty string")

        def attach(function: EffectHandler) -> EffectHandler:
            if not callable(function):
                raise TypeError("effect handler must be callable")
            if name in self._handlers:
                raise ValueError(f"effect already registered: {name}")
            self._handlers[name] = EffectRegistration(name, function)
            return function

        return attach if handler is None else attach(handler)

    def names(self) -> tuple[str, ...]:
        """Return deterministic names for diagnostics and coverage tooling."""

        return tuple(sorted(self._handlers))

    def dispatch(self, name: str, state: dict, item: dict, rng: Any) -> bool:
        """Run an explicit handler and return its completion flag."""

        registration = self._handlers.get(name)
        if registration is None:
            raise UnknownEffectError(f"unregistered effect: {name}")
        completed = registration.handler(state, item, rng)
        if type(completed) is not bool:
            raise TypeError(f"effect handler {name!r} must return bool")
        return completed

