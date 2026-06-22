"""Unit test style behaviour: tri-state combine, SGR generation, parse."""

from fastrich.style import NULL_STYLE, Style


def test_null_is_falsy_and_renders_plain() -> None:
    """Test that NULL_STYLE is falsy and renders plain text."""
    assert not NULL_STYLE
    assert NULL_STYLE.sgr == ""
    assert NULL_STYLE.render("x") == "x"


def test_sgr_codes() -> None:
    """Test that SGR codes are generated correctly."""
    assert Style(bold=True).sgr == "\x1b[1m"
    assert Style(color="red").sgr == "\x1b[31m"
    assert Style(bgcolor="blue").sgr == "\x1b[44m"
    assert Style(color="bright_red").sgr == "\x1b[91m"
    assert Style(bold=True, color="red").sgr == "\x1b[1;31m"


def test_render_wraps_with_reset() -> None:
    """Test that render wraps text with reset."""
    assert Style(bold=True).render("hi") == "\x1b[1mhi\x1b[0m"


def test_combine_overrides_set_fields_only() -> None:
    """Test that combine overrides set fields only."""
    base = Style(bold=True, color="red")
    over = Style(color="green")
    merged = base.combine(over)
    assert merged.bold is True  # Inherited
    assert merged.color == "green"  # Overridden
    assert (base + over) == merged  # __add__ alias


def test_combine_with_null_is_identity() -> None:
    """Test that combine with NULL_STYLE is identity."""
    s = Style(italic=True)
    assert s.combine(NULL_STYLE) is s


def test_equality_and_hash() -> None:
    """Test that equality and hash are implemented correctly."""
    assert Style(bold=True) == Style(bold=True)
    assert hash(Style(bold=True)) == hash(Style(bold=True))
    assert Style(bold=True) != Style(bold=False)


def test_parse_vocabulary() -> None:
    """Test that parse vocabulary works correctly."""
    assert Style.parse("bold red") == Style(bold=True, color="red")
    assert Style.parse("italic on blue") == Style(italic=True, bgcolor="blue")
    assert Style.parse("on bright_white") == Style(bgcolor="bright_white")


def test_parse_is_cached() -> None:
    """Test that parse is cached."""
    assert Style.parse("bold red") is Style.parse("bold red")
