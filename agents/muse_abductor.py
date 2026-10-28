"""T-4.2 Three single-turn, schema-validated abductor roles.

Each role is one deterministic function call with Pydantic-validated input
and output -- no agentic loop, no hidden state. The claim extractor harvests
structured claims from prose; the rival writer frames the canonical rival
sets per scenario; the brief writer composes annotated statements whose
every number, relation, and entity the verification gate can check.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

Strict = ConfigDict(extra="forbid")

_RCC8 = r"DC|EC|PO|EQ|TPPi|NTPPi|TPP|NTPP"
_CELL = r"-?\d+\.\d,-?\d+\.\d"


class Claim(BaseModel):
    model_config = Strict
    text: str
    entities: list[str] = Field(default_factory=list)
    relations: list[str] = Field(default_factory=list)
    numbers: list[float] = Field(default_factory=list)
    source: str = ""


class RivalSet(BaseModel):
    model_config = Strict
    claim_id: str
    scenario: str
    rivals: list[str]


class Statement(BaseModel):
    model_config = Strict
    text: str
    entities: list[str] = Field(default_factory=list)
    relations: list[str] = Field(default_factory=list)
    numbers: list[float] = Field(default_factory=list)


class Brief(BaseModel):
    model_config = Strict
    title: str
    statements: list[Statement]


def extract_claims(text: str, source: str = "") -> list[Claim]:
    """Role 1: harvest structured claims from prose (one sentence each)."""
    claims = []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        if not sent:
            continue
        claims.append(Claim(
            text=sent,
            entities=sorted(set(re.findall(_CELL, sent))),
            relations=sorted(set(re.findall(rf"\b({_RCC8})\b", sent))),
            numbers=[float(n) for n in re.findall(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])", sent)
                     if not (1900 <= float(n) <= 2100 and "." not in n)],
            source=source,
        ))
    return claims


def write_rivals(claim_id: str, scenario: str) -> RivalSet:
    """Role 2: frame the canonical rival set for a claim (predicates live in
    the auditor; this role only names the rivals to test)."""
    if scenario == "fire_kalimantan":
        rivals = ["extinction", "smoldering", "boundary_hopping", "evasion"]
    else:
        rivals = ["free_drainage", "impoundment"]
    return RivalSet(claim_id=claim_id, scenario=scenario, rivals=rivals)


def write_brief(topic: str, facts: list[dict]) -> Brief:
    """Role 3: compose annotated statements. Every number/relation/entity a
    statement cites must be listed in its annotations for the gate."""
    return Brief(title=topic, statements=[Statement(**f) for f in facts])
