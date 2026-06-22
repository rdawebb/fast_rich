"""Text behaviour: construction, span layering, measurement, RLE render."""

from fastrich.style import Style
from fastrich.text import Text


def test_plain_render_and_len() -> None:
    """Test plain text rendering and length."""
    t = Text("hello")
    assert t.render() == "hello"
    assert len(t) == 5
    assert t.cell_len == 5


def test_cell_len_uses_width_engine() -> None:
    """Test cell length uses width engine."""
    assert Text("日本語").cell_len == 6
    assert Text("\U0001f1ec\U0001f1e7").cell_len == 2  # GB flag


def test_append_styled() -> None:
    """Test appending styled text."""
    t = Text("level: ").append("ERROR", Style(bold=True, color="red"))
    assert t.plain == "level: ERROR"
    assert t.render() == "level: \x1b[1;31mERROR\x1b[0m"


def test_stylise_range() -> None:
    """Test stylising a range of text."""
    t = Text("abcdef")
    t.stylise(Style(underline=True), 2, 4)
    assert t.render() == "ab\x1b[4mcd\x1b[0mef"


def test_overlapping_spans_layer_in_order() -> None:
    """Test overlapping spans layer in order."""
    t = Text("xy")
    t.stylise(Style(bold=True), 0, 2)
    t.stylise(Style(color="green"), 1, 2)

    # pos 0: bold ; pos 1: bold+green
    assert t.render() == "\x1b[1mx\x1b[0m\x1b[1;32my\x1b[0m"


def test_base_style_applies_to_whole() -> None:
    """Test base style applies to whole text."""
    t = Text("hi", style=Style(dim=True))
    assert t.render() == "\x1b[2mhi\x1b[0m"


def test_empty_text_renders_empty() -> None:
    """Test empty text renders empty."""
    assert Text("").render() == ""
