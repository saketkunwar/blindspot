"""T-4.3 Verification gate: default deny.

Every relation code, number, and entity name in a brief is checked against
the ledger. Strip mode removes offending statements (recording why); block
mode rejects the whole brief on the first unverified item. An empty ledger
establishes no claim, so every annotated statement is stripped and the brief
comes back number-free.
"""
from __future__ import annotations

import re

from agents.muse_abductor import Brief, Statement

_RCC8 = r"DC|EC|PO|EQ|TPPi|NTPPi|TPP|NTPP"
_ALLEN = {"b", "m", "o", "s", "d", "f", "eq", "fi", "di", "si", "oi", "mi", "bi"}
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_NUM = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)(?![\w.])")


def _close(a: float, b: float, rel: float = 1e-6) -> bool:
    return abs(a - b) <= max(1e-9, rel * max(abs(a), abs(b)))


def _text_numbers(text: str) -> list[float]:
    text = _ISO_DATE.sub("", text)
    return [float(n) for n in _NUM.findall(text)
            if not (1900 <= float(n) <= 2100 and "." not in n)]


def _statement_violations(st: Statement, ledger: dict) -> list[str]:
    bad = []
    for e in st.entities:
        if e not in ledger["entities"]:
            bad.append(f"unverified entity {e!r}")
    for r in st.relations:
        if r not in ledger["relations"]:
            bad.append(f"unverified relation {r!r}")
    for n in st.numbers:
        if not any(_close(n, m) for m in ledger["numbers"]):
            bad.append(f"unverified number {n}")
    # Text scan runs on the text with annotated entities blanked out, so the
    # digits inside ids like "bridges:7" or "10.0,0.0" do not count as claims.
    masked = st.text
    for e in st.entities:
        masked = masked.replace(e, " ")
    for code in re.findall(rf"\b({_RCC8})\b", masked):
        if code not in ledger["relations"]:
            bad.append(f"unverified relation in text {code!r}")
    for code in re.findall(r'"([a-z]{1,2})"', masked):
        if code in _ALLEN and code not in ledger["relations"]:
            bad.append(f"unverified Allen code in text {code!r}")
    for n in _text_numbers(masked):
        if not any(_close(n, m) for m in st.numbers):
            bad.append(f"unannotated number in text {n}")
    return bad


def check(brief: Brief, ledger: dict, mode: str = "strip") -> tuple[bool, Brief | None, list[str]]:
    """Returns (ok, brief_or_none, violations). Strip keeps verified
    statements; block rejects the brief on any violation."""
    assert mode in ("strip", "block")
    kept, violations = [], []
    for st in brief.statements:
        problems = _statement_violations(st, ledger)
        if problems:
            violations += [f"{st.text[:60]}...: {p}" for p in problems]
            if mode == "block":
                return False, None, violations
        else:
            kept.append(st)
    return True, Brief(title=brief.title, statements=kept), violations
