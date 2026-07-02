"""Unit tests for measurement protocol + natural-width layout."""

from fastrich.align import Align
from fastrich.box import ASCII
from fastrich.measure import Measurement, measure
from fastrich.table import Table
from fastrich.text import Text


def test_measure_str(make_console) -> None:
    """Test that measure_str returns the correct Measurement."""
    c = make_console()
    assert measure(c, "hello world", c.options) == Measurement(5, 11)


def test_measure_str_clamped_to_width(make_console) -> None:
    """Test that measure_str is clamped to the available width."""
    c = make_console(width=8)
    # maximum can't exceed available width
    assert measure(c, "hello world", c.options) == Measurement(5, 8)


def test_text_measure(make_console) -> None:
    """Test that Text.__rich_measure__ returns the correct Measurement."""
    c = make_console()
    assert Text("ab cde").__rich_measure__(c, c.options) == Measurement(3, 6)


def test_table_measure_natural_width(make_console) -> None:
    """Test that Table.__rich_measure__ returns the correct Measurement."""
    t = Table("A", "B", box=ASCII)
    t.add_row("1", "2")

    # Widths [1,1], overhead = (ncols+1) + 2*pad*ncols = 3 + 4 = 7 -> max 9
    c = make_console()
    m = t.__rich_measure__(c, c.options)
    assert m.maximum == 9


def test_normalise_orders_bounds() -> None:
    """Test that Measurement.normalise orders bounds correctly."""
    assert Measurement(10, 3).normalise() == Measurement(3, 3)


def test_align_centers_table_via_measurement(make_console) -> None:
    """Test that Align.center centers a table via Measurement."""
    t = Table("A", "B", box=ASCII)
    t.add_row("1", "2")  # Natural width 9
    c = make_console(width=30)
    c.print(Align.center(t))
    first = c.file.getvalue().splitlines()[0]
    assert first == b" " * 10 + b"+---+---+" + b" " * 11
