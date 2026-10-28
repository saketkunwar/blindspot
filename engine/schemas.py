"""T-1.1 Strict Pydantic v2 models for the kernel, pipelines, agents and API.

A ``None`` anywhere in the preregistered config means "not decided": loading
raises :class:`ConfigIncomplete` and code must never substitute a default.
"""
from __future__ import annotations

import pathlib
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

Strict = ConfigDict(extra="forbid")


class ConfigIncomplete(Exception):
    """Raised when a preregistered config value is still null."""


def _null_paths(node: Any, prefix: str = "") -> list[str]:
    if isinstance(node, dict):
        out: list[str] = []
        for key, val in node.items():
            out += _null_paths(val, f"{prefix}.{key}" if prefix else str(key))
        return out
    if node is None:
        return [prefix]
    return []


def load_preregistered(path: str | pathlib.Path = "config/preregistered.yaml") -> dict:
    """Load preregistered config; raise ConfigIncomplete on any null value."""
    cfg = yaml.safe_load(pathlib.Path(path).read_text())
    nulls = _null_paths(cfg)
    if nulls:
        raise ConfigIncomplete(f"preregistered config undecided at: {', '.join(nulls)}")
    return cfg


class Rcc8Value(BaseModel):
    model_config = Strict
    relation: Literal["DC", "EC", "PO", "EQ", "TPP", "NTPP", "TPPi", "NTPPi"]
    status: Literal["ENTAILED", "POSSIBLE", "CONTRADICTION"]


class Snapshot(BaseModel):
    """§5 output contract for one directed snapshot(A, B)."""

    model_config = Strict
    rcc8: Rcc8Value
    rectangle: list[str] = Field(min_length=2, max_length=2)
    tiles: list[str]
    bearing: str
    edge_gap_m: float = Field(ge=0)
    centroid_dist_km: float = Field(ge=0)
    band: Literal["CONTACT", "IMMEDIATE_ENVELOPE", "NEAR", "MEDIUM", "FAR"]


class Hypothesis(BaseModel):
    model_config = Strict
    id: str
    supports: list[str] = Field(default_factory=list)
    refutes: list[str] = Field(default_factory=list)
    status: Literal["SUPPORTED", "FALSIFIED", "OPEN"]


class DetectorVerdict(BaseModel):
    model_config = Strict
    triggered: bool
    reason: str
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence: list[Any] = Field(default_factory=list)


class State(BaseModel):
    """Qualitative state of one tracked entity at one time."""

    model_config = Strict
    id: str
    at: str
    rcc8: dict[str, str] = Field(default_factory=dict)
    rectangle: list[str] = Field(default_factory=list)
    tiles: list[str] = Field(default_factory=list)
    band: str = ""


class Transition(BaseModel):
    model_config = Strict
    entity: str
    from_state: str
    to_state: str
    kind: Literal["CONTINUOUS", "DISCONTINUOUS_JUMP"] = "CONTINUOUS"
    missing_intermediates: list[str] = Field(default_factory=list)


class GapReceipt(BaseModel):
    """What was known when the sensing gap opened."""

    model_config = Strict
    scenario: str
    entity: str
    gap_start: str
    gap_end: str
    last_state: State
    v_max_m_per_hr: float = Field(gt=0)


class Insight(BaseModel):
    model_config = Strict
    id: str
    text: str
    relations: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    verdict: str = "OPEN"
