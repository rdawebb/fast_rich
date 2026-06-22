"""Unit tests for console behaviour: capabilities, color policy, render protocol, output."""

import io
from typing import Iterable

import pytest

from fastrich.console import Console
from fastrich.style import Style
from fastrich.text import Text


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch) -> None:
    """Clear environment variables that may affect console behavior.

    Args:
        monkeypatch: Pytest fixture for modifying environment variables.
    """
    for var in ("NO_COLOR", "FORCE_COLOR", "COLORTERM", "TERM", "COLUMNS"):
        monkeypatch.delenv(var, raising=False)


def _console(**kw) -> Console:
    """Create a Console instance with default file and width settings.

    Args:
        **kw: Additional keyword arguments to pass to the Console constructor.

    Returns:
        The created Console instance.
    """
    kw.setdefault("file", io.StringIO())

    return Console(**kw)


def test_width_override_and_size() -> None:
    """Test that width override and size are correctly applied to the Console instance."""
    c = _console(width=20)
    assert c.width == 20
    assert c.size == (20, 25)


def test_color_disabled_strips_sgr() -> None:
    """Test that color disabled strips SGR escape sequences from output."""
    buf = io.StringIO()
    c = _console(color_system=None, file=buf)
    c.print("ERROR", style="bold red")
    assert buf.getvalue() == "ERROR\n"


def test_color_enabled_emits_sgr() -> None:
    """Test that color enabled emits SGR escape sequences in output."""
    buf = io.StringIO()
    c = _console(color_system="standard", force_terminal=True, width=20, file=buf)
    c.print("ERROR", style="bold red")
    assert buf.getvalue() == "\x1b[1;31mERROR\x1b[0m\n"


def test_no_color_env_wins(monkeypatch) -> None:
    """Test that NO_COLOR environment variable wins over force_terminal setting."""
    monkeypatch.setenv("NO_COLOR", "1")
    c = _console(force_terminal=True)
    assert c.no_color is True


def test_force_color_marks_terminal(monkeypatch) -> None:
    """Test that FORCE_COLOR environment variable marks terminal as color-capable."""
    monkeypatch.setenv("FORCE_COLOR", "1")
    c = _console()
    assert c.is_terminal is True
    assert c.color_system == "standard"


def test_auto_detects_truecolor(monkeypatch) -> None:
    """Test that COLORTERM environment variable auto-detects truecolor."""
    monkeypatch.setenv("COLORTERM", "truecolor")
    c = _console(force_terminal=True)
    assert c.color_system == "truecolor"


def test_non_terminal_defaults_to_no_color() -> None:
    """Test that non-terminal defaults to no color."""
    c = _console()  # StringIO is not a tty
    assert c.color_system is None


def test_render_protocol_recurses() -> None:
    """Test that render protocol recurses correctly."""

    class Banner:
        """A banner that uses rich console protocol to render itself."""

        def __rich_console__(self, console, options) -> Iterable[Text]:
            """Yield the banner's text, including styled 'hi' in the middle.

            Args:
                console: The console instance to render with.
                options: The render options.

            Yields:
                The banner's text, including styled 'hi' in the middle.
            """
            yield "== "
            yield Text("hi", style=Style(bold=True))
            yield " =="

    c = _console(color_system="standard", force_terminal=True)
    assert c.render_str(Banner()) == "== \x1b[1mhi\x1b[0m =="


def test_print_joins_and_terminates() -> None:
    """Test that print joins and terminates correctly."""
    buf = io.StringIO()
    c = _console(color_system=None, file=buf)
    c.print("a", "b", sep="-", end="!")
    assert buf.getvalue() == "a-b!"
