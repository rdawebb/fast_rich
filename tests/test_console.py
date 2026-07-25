"""Unit tests for console behaviour: capabilities, color policy, render protocol, output."""

import io
from collections.abc import Iterable

from fastrich.console import Console
from fastrich.style import Style
from fastrich.text import Text


def test_console_height(make_console) -> None:
    """Test that a configured height is reported by size/height."""
    c = make_console(width=10, height=7)
    assert c.height == 7
    assert c.size == (10, 7)


def test_width_override_and_size(make_console) -> None:
    """Test that width override and size are correctly applied to the Console instance."""
    c = make_console(width=20)
    assert c.width == 20
    assert c.size == (20, 25)


def test_color_disabled_strips_sgr(make_console) -> None:
    """Test that color disabled strips SGR escape sequences from output."""
    c = make_console(color=None)
    c.print("ERROR", style="bold red")
    assert c.file.getvalue() == b"ERROR\n"


def test_color_enabled_emits_sgr(make_console) -> None:
    """Test that color enabled emits SGR escape sequences in output."""
    c = make_console(color="standard", width=20)
    c.print("ERROR", style="bold red")
    assert c.file.getvalue() == b"\x1b[1;31mERROR\x1b[0m\n"


def test_no_color_env_wins(monkeypatch, make_console) -> None:
    """Test that NO_COLOR environment variable wins over force_terminal setting."""
    monkeypatch.setenv("NO_COLOR", "1")
    c = make_console(color="auto", force_terminal=True)
    assert c.no_color is True


def test_console_no_color_override(make_console) -> None:
    """Test that no_color=True disables color despite a color system."""
    c = make_console(
        color="standard",
        no_color=True,
    )
    c.print("[red]hi[/]")
    assert c.file.getvalue() == b"hi\n"


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
    c = make_console(color="auto", force_terminal=None)  # in-memory sink is not a tty
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
    assert c.file.getvalue() == b"a-b!"


def test_resolve_writer_emits_bytes_via_buffer() -> None:
    """Test that a text stream with a binary .buffer (the stdout path) gets raw bytes."""
    buf = io.BytesIO()
    c = Console(file=io.TextIOWrapper(buf, encoding="utf-8"), color_system=None)
    c.print("hi")
    assert buf.getvalue() == b"hi\n"


def test_resolve_writer_emits_bytes_to_binary_sink() -> None:
    """Test that a native binary sink receives raw bytes directly."""
    buf = io.BytesIO()
    c = Console(file=buf, color_system=None)
    c.print("hi")
    assert buf.getvalue() == b"hi\n"


def test_resolve_writer_decodes_for_text_sink() -> None:
    """Test that a pure text sink (no .buffer) receives decoded str."""
    buf = io.StringIO()
    c = Console(file=buf, color_system=None)
    c.print("hi")
    assert buf.getvalue() == "hi\n"


def test_print_wraps_string_to_width(make_console) -> None:
    """Test that a standalone printed string wraps ragged to the console width."""
    c = make_console(width=12)
    c.print("one two three four five")
    assert c.file.getvalue() == b"one two\nthree four\nfive\n"


def test_print_justify_override(make_console) -> None:
    """Test that print's justify overrides a Text's own justify (print wins)."""
    c = make_console(width=8)
    c.print(Text("hi", justify="center"), justify="right")
    assert c.file.getvalue() == b"      hi\n"


def test_print_string_no_trailing_pad(make_console) -> None:
    """Test that an unset justify wraps ragged (no trailing padding)."""
    c = make_console(width=20)
    c.print("short")
    assert c.file.getvalue() == b"short\n"  # Not padded to width


def test_print_overflow_override(make_console) -> None:
    """Test that print's overflow override truncates a long unwrapped word."""
    c = make_console(width=6)
    c.print("supercalifragilistic", overflow="ellipsis", no_wrap=True)
    assert c.file.getvalue() == "super\u2026\n".encode()


def test_console_stderr_sink() -> None:
    """Test that stderr=True selects sys.stderr when no file is given."""
    import sys

    c = Console(stderr=True)
    assert c.file is sys.stderr


def test_console_soft_wrap_default(make_console) -> None:
    """Test that soft_wrap emits text unwrapped (terminal wraps it)."""
    c = make_console(color=None, width=8, soft_wrap=True)
    c.print("one two three four")
    assert c.file.getvalue() == b"one two three four\n"


def test_print_soft_wrap_override(make_console) -> None:
    """Test that a per-print soft_wrap overrides the console default."""
    c = make_console(color=None, width=8)
    c.print("one two three four", soft_wrap=True)
    assert c.file.getvalue() == b"one two three four\n"
