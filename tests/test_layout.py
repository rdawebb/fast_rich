"""Align and Columns layout primitives."""

from fastrich.align import Align
from fastrich.columns import Columns


def test_align_left(render) -> None:
    """Test that Align.left aligns the renderable to the left."""
    assert render(Align("hi", "left"), width=10) == "hi        \n"


def test_align_center(render) -> None:
    """Test that Align.center aligns the renderable to the center."""
    assert render(Align.center("hi"), width=10) == "    hi    \n"


def test_align_right(render) -> None:
    """Test that Align.right aligns the renderable to the right."""
    assert render(Align.right("hi"), width=10) == "        hi\n"


def test_align_vertical_middle(render) -> None:
    """Test that Align.vertical aligns the renderable to the middle."""
    out = render(Align("x", "left", vertical="middle", height=3), width=4)
    assert out == "    \nx   \n    \n"


def test_columns_single_row(render) -> None:
    """Test that Columns renders a single row of renderables."""
    # Default: no padding, equal=False
    assert render(Columns(["one", "two", "three"]), width=20) == "one two three\n"


def test_columns_wraps_to_rows(render) -> None:
    """Test that Columns wraps to rows when the width is exceeded."""
    # col_w 1, gutter 1 -> 2 columns fit in width 3
    assert render(Columns(["a", "b", "c", "d"]), width=3) == "a b\nc d\n"


def test_columns_equal_affects_count_not_widths(render) -> None:
    """Test that equal=True only drives the column count; rendered columns still size to content (as Rich)."""
    assert render(Columns(["aa", "b"], equal=True), width=20) == "aa b\n"
    assert render(Columns(["a", "bbbb", "c"], equal=True), width=30) == "a bbbb c\n"


def test_columns_equal_wrapping(render) -> None:
    """Test that equal=True wraps as if every item were the widest, with per-column content widths."""
    out = render(Columns(["a", "bbbb", "c", "dd", "e", "fff"], equal=True), width=10)
    assert out == "a bbbb\nc dd  \ne fff \n"


def test_columns_empty(render) -> None:
    """Test that Columns with no renderables prints nothing at all (as Rich)."""
    assert render(Columns([]), width=10) == ""


def test_columns_default_packs_varying_widths(render) -> None:
    """Test that the default fit uses per-column maxima, not the widest item."""
    out = render(Columns(["aaaaaaaaaaaaaaaaaaaa", "b", "c", "d"]), width=40)
    assert out == "aaaaaaaaaaaaaaaaaaaa b c d\n"  # One row of four columns


def test_columns_default_sizes_each_column(render) -> None:
    """Test that the default sizes each column to its own contents."""
    out = render(Columns(["a", "bbbb", "c"]), width=30).splitlines()[0]
    assert out == "a bbbb c"  # No uniform padding


def test_columns_trailing_blank_cells_padded(render) -> None:
    """Test that missing trailing cells render as blanks padded to the table width (as Rich)."""
    out = render(Columns(["aa", "bb", "cc", "dd", "ee"]), width=5)
    assert out == "aa bb\ncc dd\nee   \n"


def test_columns_column_first_fills_down(render) -> None:
    """Test that column_first fills down each column before moving right."""
    items = ["a", "b", "c", "d"]
    rows = render(Columns(items, column_first=True), width=3).splitlines()
    assert rows[0] == "a c"  # Down column 0 first: a, b
    assert rows[1] == "b d"


def test_columns_column_first_balances_columns(render) -> None:
    """Test that column_first balances column lengths: n//ncols each, first n%ncols get one extra."""
    items = ["aaaa", "b", "cc", "d", "eee", "f", "g"]
    out = render(Columns(items, column_first=True), width=12)
    # Three columns of lengths [3, 2, 2], not ceil-filled [3, 3, 1]
    assert out == "aaaa d   f\nb    eee g\ncc        \n"


def test_columns_overflow_ellipsis(render) -> None:
    """Test that an over-wide word truncates with an ellipsis on one line (as Rich table cells)."""
    out = render(Columns(["aaaaaaaaaa", "b"]), width=6)
    assert out == "aaaaa…\nb     \n"


def test_columns_fixed_width_count(render) -> None:
    """Test that a fixed width divides the space Rich's way: avail // (width + gutter)."""
    out = render(Columns(["a", "b", "c", "d", "e"], width=5), width=23)
    assert out == "a     b     c    \nd     e          \n"  # Still 3 columns at 23


def test_columns_int_padding_adds_vertical_gap(render) -> None:
    """Test that int padding pads all four sides: one blank line between rows, none at edges."""
    out = render(Columns(["a", "b", "c", "d"], padding=1), width=5)
    assert out == "a b c\n     \nd    \n"


def test_columns_expand_distributes_by_width(render) -> None:
    """Test that expand=True spreads the leftover proportionally to padded column widths (as Rich)."""
    out = render(Columns(["a", "bb", "c"], expand=True), width=20)
    assert out == "a      bb        c  \n"


def test_columns_multiline_item_sets_row_height(render) -> None:
    """Test that a multi-line item makes its whole row that tall, other cells blank-filled."""
    out = render(Columns(["a\nbb", "ccc", "d"]), width=12)
    assert out == "a  ccc d\nbb      \n"


def test_rule_end_default_and_override(make_console) -> None:
    """Test that Rule.end controls the trailing text, and print's end wins."""
    from fastrich.rule import Rule

    c = make_console(width=6)
    c.print(Rule(end=""))
    assert c.file.getvalue() == "──────".encode()  # No trailing newline

    c2 = make_console(width=6)
    c2.print(Rule(end=""), end="!")
    assert c2.file.getvalue().endswith(b"!")  # Explicit end takes precedence
