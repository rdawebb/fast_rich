"""Unit tests for emoji shortcode substitution and the markup hooks."""

import pytest

from fastrich.emoji import replace


@pytest.mark.parametrize(
    "text, expected",
    [
        ("go :rocket:", "go \U0001f680"),  # known shortcode -> glyph
        ("a :not_a_real_code: b", "a :not_a_real_code: b"),  # unknown left untouched
        ("meet at 10:30", "meet at 10:30"),  # stray colons (times) ignored
        ("no codes here", "no codes here"),  # no colon -> unchanged
    ],
)
def test_replace(text, expected) -> None:
    """Test shortcode replacement across known, unknown, and non-code inputs."""
    assert replace(text) == expected


def test_console_fast_path_emoji(render) -> None:
    """Test emoji substitution on the single plain-string fast path."""
    assert render("build :fire: done", width=40) == "build \U0001f525 done\n"


def test_console_markup_path_emoji(render) -> None:
    """Test emoji substitution inside markup, not in tag bodies."""
    assert render("[bold]:star:[/]", width=40) == "\u2b50\n"


def test_console_emoji_disabled(render) -> None:
    """Test that emoji=False leaves shortcodes verbatim."""
    assert render("build :rocket:", width=40, emoji=False) == "build :rocket:\n"


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


def test_literal_emoji_used_in_string(render) -> None:
    """Test that literal emoji characters are not replaced."""
    assert render("build 🔥 done", width=40) == "build \U0001f525 done\n"
