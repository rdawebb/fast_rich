"""Unit tests for markup parsing into styled Text."""

from fastrich.style import Style
from fastrich.text import Text


def _runs(text: Text) -> list[tuple[str, Style | None]]:
    """Return the runs (text/color pairs) of a Text object.

    Args:
        text: The Text object to extract runs from.

    Returns:
        The list of runs (text/color pairs).
    """
    return [(s.text, s.style) for s in text._segments()]


def test_simple_tag() -> None:
    """Test that a simple tag is parsed correctly."""
    t = Text.from_markup("[bold]hi[/]")
    assert _runs(t) == [("hi", Style(bold=True))]


def test_nested_layers_inner_over_outer() -> None:
    """Test that nested layers with inner over outer are parsed correctly."""
    t = Text.from_markup("[bold]A[red]B[/red]C[/bold]")
    assert _runs(t) == [
        ("A", Style(bold=True)),
        ("B", Style(bold=True, color="red")),
        ("C", Style(bold=True)),
    ]


def test_close_all_shorthand() -> None:
    """Test that close-all shorthand is parsed correctly."""
    t = Text.from_markup("[italic]x[/]")
    assert _runs(t) == [("x", Style(italic=True))]


def test_named_close_matches() -> None:
    """Test that named close matches are parsed correctly."""
    t = Text.from_markup("[bold][red]x[/bold] y[/red]")

    # Bold closes mid-stream, red continues over the space + y
    runs = _runs(t)
    assert runs[0] == ("x", Style(bold=True, color="red"))
    assert runs[1] == (" y", Style(color="red"))


def test_escape_literal_bracket() -> None:
    """Test that escape literal bracket is parsed correctly."""
    t = Text.from_markup(r"\[notag]")
    assert t.plain == "[notag]"
    assert _runs(t) == [("[notag]", None)]


def test_plain_passthrough() -> None:
    """Test that plain passthrough is parsed correctly."""
    t = Text.from_markup("just text")
    assert t.plain == "just text"
    assert _runs(t) == [("just text", None)]


def test_on_background() -> None:
    """Test that on background is parsed correctly."""
    t = Text.from_markup("[on blue]x[/]")
    assert _runs(t) == [("x", Style(bgcolor="blue"))]
