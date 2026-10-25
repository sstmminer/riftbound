"""Self-play orchestration: policies never receive the engine or an audit log."""

import copy
import random
from dataclasses import dataclass
from typing import Protocol

from .engine import Action, Environment


class Policy(Protocol):
    def choose(self, observation: dict, legal_actions: tuple[Action, ...]) -> Action: ...


class RandomPolicy:
    def __init__(self, seed: int):
        self._rng = random.Random(seed)

    def choose(self, observation: dict, legal_actions: tuple[Action, ...]) -> Action:
        return self._rng.choice(legal_actions)


@dataclass
class Episode:
    decisions: list[dict]
    rewards: tuple[float, float]
    terminated: bool
    truncated: bool


def self_play(env: Environment, policies: tuple[Policy, Policy], *, seed: int) -> Episode:
    """Returned decisions are perspective-labeled; not safe opponent observations.

    A dataset contains both players' private observations. Feed each decision
    only to its own policy; never include future decisions in policy input.
    """
    if len(policies) != 2:
        raise ValueError("exactly two policies are required")
    env.reset(seed=seed)
    decisions: list[dict] = []
    rewards = env.rewards
    while not env.done:
        player = env.current_player
        observation, legal = env.observe(player), env.legal_actions()
        # The policy is allowed to mutate its inputs without corrupting the record.
        action = policies[player].choose(copy.deepcopy(observation), legal)
        transition = env.step(action)
        decisions.append({"player": player, "observation": observation,
                          "legal_actions": [a.to_dict() for a in legal],
                          "action": action.to_dict()})
        rewards = transition.rewards
    return Episode(decisions, rewards, env.terminated, env.truncated)
