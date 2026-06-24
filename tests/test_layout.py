"""Align and Columns layout primitives."""

import io

from fastrich.columns import Columns

from fastrich.align import Align
from fastrich.console import Console


def _plain(renderable, width):
    c = Console(file=io.StringIO(), color_system=None, width=width)
    c.print(renderable)
    return c.file.getvalue()


def test_align_left():
    assert _plain(Align("hi", "left"), 10) == "hi        \n"


def test_align_center():
    assert _plain(Align.center("hi"), 10) == "    hi    \n"


def test_align_right():
    assert _plain(Align.right("hi"), 10) == "        hi\n"


def test_align_vertical_middle():
    out = _plain(Align("x", "left", vertical="middle", height=3), 4)
    assert out == "    \nx   \n    \n"


def test_columns_single_row():
    assert _plain(Columns(["one", "two", "three"]), 20) == "one   two   three\n"


def test_columns_wraps_to_rows():
    # col_w 1, gutter 1 -> 2 columns fit in width 3
    assert _plain(Columns(["a", "b", "c", "d"]), 3) == "a b\nc d\n"


def test_columns_equal_width_padding():
    # widest item sets the column width; shorter items pad to it
    out = _plain(Columns(["aa", "b"]), 20)
    assert out == "aa b \n"  # col_w 2: 'aa' + gutter + 'b '


def test_columns_empty():
    assert _plain(Columns([]), 10) == "\n"
