"""Static check: no code in ict_lab (outside tests) divides by adjusted OHLC prices or uses
pct_change on price columns. Back-adjusted prices are only meaningful as differences.
Suppress a deliberate, justified exception with the comment  # price-division-ok  on that line."""
import ast
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parents[1]
PRICE_NAMES = {"open", "high", "low", "close", "adj_open", "adj_high", "adj_low", "adj_close", "price", "px"}


def _ident(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Subscript):
        s = node.slice
        if isinstance(s, ast.Constant) and isinstance(s.value, str):
            return s.value
        if isinstance(s, ast.List):   # df[["open","close"]]
            vals = [e.value for e in s.elts if isinstance(e, ast.Constant)]
            return next((v for v in vals if v in PRICE_NAMES), None)
    return None


def scan_source(src: str, filename: str = "<src>") -> list[str]:
    tree = ast.parse(src, filename)
    lines = src.splitlines()
    hits = []
    for node in ast.walk(tree):
        line = lines[node.lineno - 1] if hasattr(node, "lineno") else ""
        if "price-division-ok" in line:
            continue
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Div, ast.FloorDiv)):
            if _ident(node.right) in PRICE_NAMES:
                hits.append(f"{filename}:{node.lineno}: division by price '{_ident(node.right)}'")
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
            if name == "pct_change":
                hits.append(f"{filename}:{node.lineno}: pct_change() on prices is not allowed")
            if name in {"log", "log1p"} and node.args and _ident(node.args[0]) in PRICE_NAMES:
                hits.append(f"{filename}:{node.lineno}: log of a price level")
    return hits


def test_scanner_catches_bad_patterns():
    bad = "r = (df['close'] - prev) / df['close']\nx = df.close.pct_change()\ny = a / close\n"
    hits = scan_source(bad)
    assert len(hits) == 3
    assert scan_source("d = (df['close'] - df['open']) / spec.tick_size\n") == []
    assert scan_source("r = x / df['close']  # price-division-ok\n") == []


def test_no_price_division_in_codebase():
    files = [p for p in LAB.rglob("*.py") if "tests" not in p.parts and "data" not in p.parts]
    assert files
    hits = []
    for p in files:
        hits += scan_source(p.read_text(), str(p.relative_to(LAB)))
    assert hits == [], "\n".join(hits)
