"""Unit tests for emoji shortcode substitution and the markup hooks."""

import io

from fastrich.console import Console
from fastrich.emoji import replace


def _plain(renderable, *, emoji: bool = True, width: int = 40) -> str:
    """Render a renderable to a plain string with emoji on/off.

    Args:
        renderable: The renderable to render.
        emoji: Whether to enable emoji substitution.
        width: The width of the console.

    Returns:
        The rendered plain string.
    """
    c = Console(file=io.StringIO(), color_system=None, width=width, emoji=emoji)
    c.print(renderable)

    return c.file.getvalue()


def test_replace_known_code() -> None:
    """Test that a known shortcode is replaced with its glyph."""
    assert replace("go :rocket:") == "go \U0001f680"


def test_replace_leaves_unknown_code() -> None:
    """Test that an unrecognised shortcode is left untouched."""
    assert replace("a :not_a_real_code: b") == "a :not_a_real_code: b"


def test_replace_ignores_stray_colons() -> None:
    """Test that lone colons (e.g. times) are not treated as shortcodes."""
    assert replace("meet at 10:30") == "meet at 10:30"


def test_replace_noop_without_colon() -> None:
    """Test that text without a colon is returned unchanged."""
    assert replace("no codes here") == "no codes here"


def test_console_fast_path_emoji() -> None:
    """Test emoji substitution on the single plain-string fast path."""
    assert _plain("build :fire: done") == "build \U0001f525 done\n"


def test_console_markup_path_emoji() -> None:
    """Test emoji substitution inside markup, not in tag bodies."""
    assert _plain("[bold]:star:[/]") == "\u2b50\n"


def test_console_emoji_disabled() -> None:
    """Test that emoji=False leaves shortcodes verbatim."""
    assert _plain("build :rocket:", emoji=False) == "build :rocket:\n"


def test_markup_style_resolver_hook() -> None:
    """Test that markup.render uses a supplied style_resolver (the Theme seam)."""
    from fastrich.markup import render
    from fastrich.style import Style

    calls = []

    def resolver(defn: str) -> Style:
        calls.append(defn)
        return Style(bold=True)

    text = render("[danger]boom[/]", style_resolver=resolver)
    assert calls == ["danger"]  # Name passed through, not parsed as SGR
    assert text.plain == "boom"


def test_markup_emoji_hook_skips_tag_bodies() -> None:
    """Test that the emoji hook only sees literal text, never tag definitions."""
    from fastrich.markup import render

    seen = []

    def hook(s: str) -> str:
        seen.append(s)
        return s

    render("[bold]hi :star:[/]", emoji_replace=hook)
    assert all("[" not in chunk and "bold" not in chunk for chunk in seen)


def test_literal_emoji_used_in_string() -> None:
    """Test that literal emoji characters are not replaced."""
    assert _plain("build 🔥 done") == "build \U0001f525 done\n"
