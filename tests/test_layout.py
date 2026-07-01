"""Align and Columns layout primitives."""

from fastrich.align import Align
from fastrich.columns import Columns


def test_align_left(render):
    assert render(Align("hi", "left"), width=10) == "hi        \n"


def test_align_center(render):
    assert render(Align.center("hi"), width=10) == "    hi    \n"


def test_align_right(render):
    assert render(Align.right("hi"), width=10) == "        hi\n"


def test_align_vertical_middle(render):
    out = render(Align("x", "left", vertical="middle", height=3), width=4)
    assert out == "    \nx   \n    \n"


def test_columns_single_row(render):
    assert render(Columns(["one", "two", "three"]), width=20) == "one   two   three\n"


def test_columns_wraps_to_rows(render):
    # col_w 1, gutter 1 -> 2 columns fit in width 3
    assert render(Columns(["a", "b", "c", "d"]), width=3) == "a b\nc d\n"


def test_columns_equal_width_padding(render):
    # widest item sets the column width; shorter items pad to it
    out = render(Columns(["aa", "b"]), width=20)
    assert out == "aa b \n"  # col_w 2: 'aa' + gutter + 'b '


def test_columns_empty(render):
    assert render(Columns([]), width=10) == "\n"
