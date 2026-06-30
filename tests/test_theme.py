"""Unit tests for Theme named-style resolution via the markup resolver hook."""

import io

from fastrich.console import Console
from fastrich.style import Style
from fastrich.theme import Theme


def _sgr(renderable, *, theme=None, style=None, width=40) -> str:
    """Render to a string with SGR codes (standard color, forced terminal)."""
    c = Console(
        file=io.StringIO(),
        color_system="standard",
        force_terminal=True,
        width=width,
        theme=theme,
    )
    c.print(renderable, style=style)
    return c.file.getvalue()


def test_theme_get_known_and_unknown() -> None:
    """Test that get returns a Style for a known name and None otherwise."""
    th = Theme({"danger": "bold red"})
    assert isinstance(th.get("danger"), Style)
    assert th.get("missing") is None


def test_theme_parses_string_values() -> None:
    """Test that string style values are parsed to Styles at construction."""
    th = Theme({"danger": "bold red"})
    assert th.get("danger") == Style.parse("bold red")


def test_theme_accepts_style_values() -> None:
    """Test that Style values pass through unchanged."""
    s = Style(bold=True)
    assert Theme({"x": s}).get("x") is s


def test_theme_inherit_false_starts_empty() -> None:
    """Test that inherit=False yields a theme with no inherited styles."""
    assert Theme(inherit=False).styles == {}


def test_console_resolves_named_style_in_markup() -> None:
    """Test that a themed name in markup resolves to its Style."""
    th = Theme({"danger": "bold red"})
    assert _sgr("[danger]boom[/]", theme=th) == "\x1b[1;31mboom\x1b[0m\n"


def test_console_resolves_named_base_style() -> None:
    """Test that a themed name passed as the base style resolves."""
    th = Theme({"danger": "bold red"})
    assert _sgr("hi", theme=th, style="danger") == "\x1b[1;31mhi\x1b[0m\n"


def test_console_unknown_name_falls_through_to_parse() -> None:
    """Test that a name absent from the theme is parsed as a definition."""
    th = Theme({"danger": "bold red"})
    assert _sgr("[bold]x[/]", theme=th) == "\x1b[1mx\x1b[0m\n"


def test_console_without_theme_unchanged() -> None:
    """Test that markup with no theme parses tags exactly as before."""
    assert _sgr("[red]y[/]") == "\x1b[31my\x1b[0m\n"


def test_theme_and_emoji_compose() -> None:
    """Test that the theme and emoji hooks are both active in one render."""
    th = Theme({"danger": "bold red"})
    out = _sgr("[danger]:fire:[/]", theme=th)
    assert out == "\x1b[1;31m\U0001f525\x1b[0m\n"
