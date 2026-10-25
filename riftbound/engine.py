"""A backend-neutral, two-player, turn-based simulator boundary.

Rule backends own timing, priority, combat and card semantics. This module never
approximates those rules. Backend state and RNG are private; policies see only
the backend's player-specific observation and legal actions.
"""

from __future__ import annotations

import copy
import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any, Protocol


class InvalidAction(ValueError):
    pass


class RulesUnavailable(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class Action:
    """JSON arguments in canonical form make actions immutable and serializable."""

    kind: str
    arguments: str = "{}"

    def __post_init__(self) -> None:
        if not self.kind or not isinstance(self.kind, str):
            raise ValueError("action kind must be a nonempty string")
        arguments = json.loads(self.arguments)
        if not isinstance(arguments, dict):
            raise ValueError("action arguments must be a JSON object")
        object.__setattr__(self, "arguments", canonical(arguments))

    @classmethod
    def make(cls, kind: str, **arguments: Any) -> Action:
        return cls(kind, canonical(arguments))

    def to_dict(self) -> dict:
        return {"kind": self.kind, "arguments": json.loads(self.arguments)}

    @classmethod
    def from_dict(cls, value: dict) -> Action:
        if set(value) != {"kind", "arguments"} or not isinstance(value["arguments"], dict):
            raise ValueError("invalid action schema")
        return cls(value["kind"], canonical(value["arguments"]))


class Rules(Protocol):
    """All state must be JSON-serializable; no mutable state on the backend.

    id identifies the exact implementation, rulebook and card-data revisions.
    legal_actions/observe/player/outcome must be pure. apply must use only the
    supplied RNG, and raise for unsupported card mechanics. outcome returns
    zero-sum terminal rewards, or None while play can continue.
    """

    id: str

    def initial_state(self, rng: random.Random) -> dict: ...
    def player(self, state: dict) -> int: ...
    def legal_actions(self, state: dict) -> tuple[Action, ...]: ...
    def observe(self, state: dict, player: int) -> dict: ...
    def apply(self, state: dict, action: Action, rng: random.Random) -> None: ...
    def outcome(self, state: dict) -> tuple[float, float] | None: ...
    def validate(self, state: dict) -> None: ...


@dataclass(frozen=True)
class Transition:
    observation: dict
    rewards: tuple[float, float]
    terminated: bool
    truncated: bool


class Environment:
    """Atomic steps, deterministic cloning and separate termination/truncation.

    This is a multi-agent API, not a Gymnasium Env. rewards are indexed by
    player, never implicitly by the next player to act.
    """

    def __init__(self, rules: Rules | None = None, *, max_steps: int = 10000):
        if rules is None:
            raise RulesUnavailable(
                "Official Riftbound backend unavailable: complete turn orchestration "
                "and tested card semantics are required. See docs/rules-coverage.md."
            )
        if type(max_steps) is not int or max_steps <= 0:
            raise ValueError("max_steps must be a positive integer")
        self._rules = rules
        self.max_steps = max_steps
        self._state: dict | None = None
        self._rng = random.Random()
        self._seed: int | None = None
        self._actions: list[Action] = []
        self._digests: list[str] = []

    def _require_reset(self) -> dict:
        if self._state is None:
            raise RuntimeError("call reset(seed=...) first")
        return self._state

    @property
    def rules_id(self) -> str:
        return self._rules.id

    @property
    def rewards(self) -> tuple[float, float]:
        outcome = self._rules.outcome(copy.deepcopy(self._require_reset()))
        return tuple(outcome) if outcome is not None else (0.0, 0.0)

    @property
    def terminated(self) -> bool:
        return self._rules.outcome(copy.deepcopy(self._require_reset())) is not None

    @property
    def truncated(self) -> bool:
        return len(self._actions) >= self.max_steps and not self.terminated

    @property
    def done(self) -> bool:
        return self.terminated or self.truncated

    @property
    def current_player(self) -> int:
        player = self._rules.player(copy.deepcopy(self._require_reset()))
        if type(player) is not int or player not in (0, 1):
            raise ValueError("backend returned invalid player")
        return player

    def reset(self, *, seed: int) -> dict:
        if type(seed) is not int:
            raise ValueError("seed must be an integer")
        rng = random.Random(seed)
        state = self._rules.initial_state(rng)
        self._rules.validate(copy.deepcopy(state))
        canonical(state)
        self._rng, self._state, self._seed = rng, state, seed
        self._actions = []
        self._digests = [self._digest()]
        return self.observe(self.current_player)

    def observe(self, player: int) -> dict:
        if type(player) is not int or player not in (0, 1):
            raise ValueError("player must be 0 or 1")
        result = self._rules.observe(copy.deepcopy(self._require_reset()), player)
        canonical(result)
        return copy.deepcopy(result)

    def legal_actions(self) -> tuple[Action, ...]:
        self._require_reset()
        if self.done:
            return ()
        result = tuple(self._rules.legal_actions(copy.deepcopy(self._state)))
        if not result or any(not isinstance(a, Action) for a in result):
            raise ValueError("nonterminal state needs valid legal actions")
        if len(set(result)) != len(result):
            raise ValueError("duplicate legal actions")
        return result

    def step(self, action: Action) -> Transition:
        if self.done:
            raise InvalidAction("episode is already finished")
        if action not in self.legal_actions():
            raise InvalidAction("action is not legal in the current state")
        # Apply to private copies: errors must not consume randomness or mutate state.
        state, rng = copy.deepcopy(self._state), copy.deepcopy(self._rng)
        self._rules.apply(state, action, rng)
        self._rules.validate(copy.deepcopy(state))
        canonical(state)
        outcome = self._rules.outcome(copy.deepcopy(state))
        if outcome is not None:
            if (len(outcome) != 2 or any(type(x) not in (int, float) for x in outcome)
                    or any(x < -1 or x > 1 for x in outcome) or sum(outcome) != 0):
                raise ValueError("invalid terminal rewards")
            canonical(outcome)
        # Validate the next observation before committing the transition.
        player = self._rules.player(copy.deepcopy(state))
        if type(player) is not int or player not in (0, 1):
            raise ValueError("backend returned invalid player")
        observation = self._rules.observe(copy.deepcopy(state), player)
        canonical(observation)
        self._state, self._rng = state, rng
        self._actions.append(action)
        self._digests.append(self._digest())
        return Transition(copy.deepcopy(observation), tuple(outcome or (0.0, 0.0)),
                          outcome is not None, self.truncated)

    def clone(self) -> Environment:
        self._require_reset()
        return copy.deepcopy(self)

    def _digest(self) -> str:
        payload = {"state": self._state, "rng": self._rng.getstate()}
        return hashlib.sha256(canonical(payload).encode()).hexdigest()

    def audit_replay(self) -> dict:
        """Privileged debugging data. NEVER give the seed to a playing policy."""
        self._require_reset()
        return {"schema": 1, "rules_id": self.rules_id, "seed": self._seed,
                "max_steps": self.max_steps,
                "actions": [a.to_dict() for a in self._actions],
                "digests": list(self._digests)}


def replay(rules: Rules, record: dict) -> Environment:
    """Check every intermediate state and RNG digest, not just the final winner."""
    if record.get("schema") != 1 or record.get("rules_id") != rules.id:
        raise ValueError("incompatible replay schema or rules revision")
    actions, digests = record["actions"], record["digests"]
    if len(digests) != len(actions) + 1:
        raise ValueError("invalid replay lengths")
    env = Environment(rules, max_steps=record["max_steps"])
    env.reset(seed=record["seed"])
    if env._digest() != digests[0]:
        raise ValueError("initial replay state mismatch")
    for index, action in enumerate(actions, 1):
        env.step(Action.from_dict(action))
        if env._digest() != digests[index]:
            raise ValueError(f"replay mismatch at step {index}")
    return env
