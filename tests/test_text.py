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


def test_text_justify_param() -> None:
    """Test that a Text's justify is used by render_lines."""
    line = Text("hi", justify="center").render_lines(6)[0]
    assert "".join(s.text for s in line) == "  hi  "


def test_text_no_wrap_uses_overflow() -> None:
    """Test that no_wrap yields a single overflow-handled line, not folded."""
    t = Text("hello world foo", no_wrap=True, overflow="ellipsis")
    lines = t.render_lines(10)
    assert len(lines) == 1
    assert "".join(s.text for s in lines[0]).endswith("\u2026")


def test_text_overflow_default_still_folds() -> None:
    """Test that overflow defaults to fold (unchanged behavior) when unset."""
    assert len(Text("hello world foo").render_lines(8)) > 1


def test_text_justify_full() -> None:
    """Test that full justify fills non-final lines and left-aligns the last."""
    lines = [
        "".join(s.text for s in ln)
        for ln in Text("the quick brown fox jumps over", justify="full").render_lines(
            20
        )
    ]
    assert all(len(ln) == 20 for ln in lines)  # Every line fits width
    assert lines[-1] == "jumps over".ljust(20)  # Last line left-aligned
    assert "  " in lines[0]  # Slack distributed as widened inter-word gaps


def test_text_justify_full_single_word() -> None:
    """Test that a one-word line can't stretch and stays left."""
    line = Text("supercalifragilistic word", justify="full").render_lines(20)[0]
    assert "".join(s.text for s in line) == "supercalifragilistic"


def test_text_justify_full_preserves_span_style() -> None:
    """Test that word styling survives full justification."""
    t = Text("alpha beta gamma delta", justify="full")
    t.stylize(Style(bold=True), 0, 5)
    line0 = t.render_lines(20)[0]
    assert any(s.style and s.style.bold and s.text == "alpha" for s in line0)


def test_text_style_string_definition() -> None:
    """Test that Text.style accepts a style definition string."""
    line = Text("hi", style="bold red").render_lines(2)[0]
    assert line[0].style == Style.parse("bold red")


def test_progress_column_style_string() -> None:
    """Test that a progress column style string flows into the cell Text."""
    import io

    from fastrich.console import Console
    from fastrich.progress import Progress, TextColumn

    p = Progress(TextColumn("{description}", style="green"))
    p.add_task("task")
    c = Console(
        file=io.BytesIO(), color_system="standard", force_terminal=True, width=40
    )
    c.file.encoding = "utf-8"
    c.print(p)
    assert b"\x1b[32m" in c.file.getvalue()
