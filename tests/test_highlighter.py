"""Unit tests for the ReprHighlighter and console highlighting."""

import io

from fastrich.console import Console
from fastrich.highlighter import NullHighlighter, ReprHighlighter
from fastrich.text import Text


def _sgr(obj, **kw) -> str:
    """Render to a string with SGR codes."""
    c = Console(
        file=io.StringIO(), color_system="standard", force_terminal=True, width=40
    )
    c.print(obj, **kw)
    return c.file.getvalue()


def test_highlight_numbers() -> None:
    """Test that numbers are highlighted (repr.number: bold cyan)."""
    assert "\x1b[1;36m42\x1b[0m" in _sgr("value = 42")


def test_highlight_bool_and_none() -> None:
    """Test that True/None are highlighted with the repr styles."""
    out = _sgr("a = True, b = None")
    assert "\x1b[3;92mTrue\x1b[0m" in out  # Italic bright_green
    assert "\x1b[3;35mNone\x1b[0m" in out  # Italic magenta


def test_highlight_string() -> None:
    """Test that a quoted string is highlighted (repr.str: green)."""
    assert "\x1b[32m'alice'\x1b[0m" in _sgr("name = 'alice'")


def test_highlight_off_per_call() -> None:
    """Test that highlight=False disables highlighting for the call."""
    assert _sgr("value = 42", highlight=False) == "value = 42\n"


def test_highlight_off_console_default() -> None:
    """Test that a console with highlight=False never highlights."""
    c = Console(
        file=io.StringIO(),
        color_system="standard",
        force_terminal=True,
        width=40,
        highlight=False,
    )
    c.print("value = 42")
    assert c.file.getvalue() == "value = 42\n"


def test_highlight_only_applies_to_strings() -> None:
    """Test that a user-supplied Text is not auto-highlighted."""
    assert _sgr(Text("value = 42")) == "value = 42\n"


def test_repr_highlighter_direct() -> None:
    """Test ReprHighlighter.highlight adds spans resolved via a resolver."""
    from fastrich.style import Style

    t = Text("42")
    ReprHighlighter().highlight(
        t, lambda name: Style(bold=True) if name == "repr.number" else None
    )
    line = t.render_lines(4)[0]
    assert any(s.style and s.style.bold for s in line)


def test_null_highlighter_noop() -> None:
    """Test that NullHighlighter adds nothing."""
    t = Text("42")
    NullHighlighter().highlight(t, lambda name: None)
    assert not t._spans


def test_custom_theme_overrides_repr_style() -> None:
    """Test that a user theme can override a repr.* style."""
    from fastrich.theme import Theme

    c = Console(
        file=io.StringIO(),
        color_system="standard",
        force_terminal=True,
        width=40,
        theme=Theme({"repr.number": "red"}),
    )
    c.print("n = 7")
    assert "\x1b[31m7\x1b[0m" in c.file.getvalue()  # Red, not the default cyan
