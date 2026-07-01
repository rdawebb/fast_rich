"""Unit tests for console behaviour: capabilities, color policy, render protocol, output."""

from typing import Iterable

from fastrich.style import Style
from fastrich.text import Text


def test_width_override_and_size(make_console) -> None:
    """Test that width override and size are correctly applied to the Console instance."""
    c = make_console(width=20)
    assert c.width == 20
    assert c.size == (20, 25)


def test_color_disabled_strips_sgr(make_console) -> None:
    """Test that color disabled strips SGR escape sequences from output."""
    c = make_console(color=None)
    c.print("ERROR", style="bold red")
    assert c.file.getvalue() == "ERROR\n"


def test_color_enabled_emits_sgr(make_console) -> None:
    """Test that color enabled emits SGR escape sequences in output."""
    c = make_console(color="standard", width=20)
    c.print("ERROR", style="bold red")
    assert c.file.getvalue() == "\x1b[1;31mERROR\x1b[0m\n"


def test_no_color_env_wins(monkeypatch, make_console) -> None:
    """Test that NO_COLOR environment variable wins over force_terminal setting."""
    monkeypatch.setenv("NO_COLOR", "1")
    c = make_console(color="auto", force_terminal=True)
    assert c.no_color is True


def test_force_color_marks_terminal(monkeypatch, make_console) -> None:
    """Test that FORCE_COLOR environment variable marks terminal as color-capable."""
    monkeypatch.setenv("FORCE_COLOR", "1")
    c = make_console(color="auto", force_terminal=None)
    assert c.is_terminal is True
    assert c.color_system == "standard"


def test_auto_detects_truecolor(monkeypatch, make_console) -> None:
    """Test that COLORTERM environment variable auto-detects truecolor."""
    monkeypatch.setenv("COLORTERM", "truecolor")
    c = make_console(color="auto", force_terminal=True)
    assert c.color_system == "truecolor"


def test_non_terminal_defaults_to_no_color(make_console) -> None:
    """Test that non-terminal defaults to no color."""
    c = make_console(color="auto", force_terminal=None)  # StringIO is not a tty
    assert c.color_system is None


def test_render_protocol_recurses(make_console) -> None:
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

    c = make_console(color="standard")
    assert c.render_str(Banner()) == "== \x1b[1mhi\x1b[0m =="


def test_print_joins_and_terminates(make_console) -> None:
    """Test that print joins and terminates correctly."""
    c = make_console(color=None)
    c.print("a", "b", sep="-", end="!")
    assert c.file.getvalue() == "a-b!"
