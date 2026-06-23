"""Test Segment pipeline: line splitting, encode-cache reuse, integration."""

import io

from fastrich.console import Console
from fastrich.segment import Segment, encode_line, split_lines
from fastrich.style import Style


def test_segment_cell_len() -> None:
    """Test that Segment.cell_len returns the correct value."""
    assert Segment("日本").cell_len == 4


def test_split_lines_basic() -> None:
    """Test that split_lines splits segments into lines on embedded newlines."""
    segs = [Segment("a\nb"), Segment("c")]
    lines = list(split_lines(segs))
    assert lines == [[Segment("a")], [Segment("b"), Segment("c")]]


def test_split_lines_preserves_style_across_break() -> None:
    """Test that split_lines preserves style across line breaks."""
    s = Style(bold=True)
    lines = list(split_lines([Segment("x\ny", s)]))
    assert lines == [[Segment("x", s)], [Segment("y", s)]]


def test_trailing_newline_yields_empty_line() -> None:
    """Test that split_lines yields an empty line after a newline."""
    assert list(split_lines([Segment("a\n")])) == [[Segment("a")], []]


def test_encode_line_is_memoised() -> None:
    """Test that encode_line is memoised."""
    line = (Segment("hello", Style(bold=True)),)
    encode_line.cache_clear()
    encode_line(line, False, "utf-8")
    encode_line(line, False, "utf-8")
    info = encode_line.cache_info()
    assert info.hits == 1 and info.misses == 1


def test_encode_line_color_policy() -> None:
    """Test that encode_line respects color policy."""
    line = (Segment("hi", Style(color="red")),)
    assert encode_line(line, True, "utf-8") == b"hi"
    assert encode_line(line, False, "utf-8") == b"\x1b[31mhi\x1b[0m"


def test_print_multiline_through_pipeline() -> None:
    """Test that print multiline text through the pipeline works correctly."""
    buf = io.StringIO()
    c = Console(file=buf, color_system=None)
    c.print("a\nb")
    assert buf.getvalue() == "a\nb\n"
