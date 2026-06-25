"""Rust/Python width parity: skipped unless the accelerator is built.

When `fastrich._width._width_rs` is present, assert it agrees with the
pure-Python reference across a representative sweep, and that the pinned
UNICODE_VERSION matches.
"""

import pytest

from fastrich._width import _width_py as py

rs = pytest.importorskip("fastrich._width._width_rs")

_SAMPLES = [
    "",
    "hello world",
    "日本語",
    "한국어",
    "ＡＢＣ",
    "café",
    "cafe\u0301",
    "a\u0300\u0301",
    "\u2602",
    "\u2602\ufe0f",
    "\u2603\ufe0e",
    "\U0001f680",
    "\U0001f44d\U0001f3fd",
    "\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466",
    "\U0001f1ec\U0001f1e7",
    "ok \U0001f680 go",
    "mixed 日本 text",
]


def test_version_matches() -> None:
    """Assert the pinned UNICODE_VERSION matches between Rust and Python implementations."""
    assert rs.UNICODE_VERSION == py.UNICODE_VERSION


@pytest.mark.parametrize("text", _SAMPLES)
def test_cell_len_parity(text) -> None:
    """Assert `cell_len` agrees between Rust and Python implementations."""
    assert rs.cell_len(text) == py.cell_len(text)


@pytest.mark.parametrize("text", _SAMPLES)
def test_cell_len_parity_cjk_policy(text) -> None:
    """Assert `cell_len` agrees between Rust and Python implementations with CJK policy."""
    assert rs.cell_len(text, True) == py.cell_len(text, True)


def test_char_width_parity_sweep() -> None:
    """Assert `char_width` agrees between Rust and Python implementations across the BMP and astral planes."""
    # Walk the BMP + a slice of the astral planes
    for cp in list(range(0x0, 0x3000)) + list(range(0x1F000, 0x1FB00)):
        assert rs.char_width(cp) == py.char_width(cp), hex(cp)
