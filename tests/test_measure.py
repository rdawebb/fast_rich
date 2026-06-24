"""Unit tests for measurement protocol + natural-width layout."""

import io

from fastrich.align import Align
from fastrich.box import ASCII
from fastrich.console import Console, ConsoleOptions
from fastrich.measure import Measurement, measure
from fastrich.table import Table
from fastrich.text import Text


def _opts(width: int = 80) -> ConsoleOptions:
    """Return a ConsoleOptions instance with the specified width.

    Args:
        width: The width of the console.

    Returns:
        The ConsoleOptions instance.
    """
    return Console(file=io.StringIO(), color_system=None, width=width).options


def _console(width: int = 80) -> Console:
    """Return a Console instance with the specified width.

    Args:
        width: The width of the console.

    Returns:
        The Console instance.
    """
    return Console(file=io.StringIO(), color_system=None, width=width)


def test_measure_str() -> None:
    """Test that measure_str returns the correct Measurement."""
    assert measure(_console(), "hello world", _opts()) == Measurement(5, 11)


def test_measure_str_clamped_to_width() -> None:
    """Test that measure_str is clamped to the available width."""
    # maximum can't exceed available width
    assert measure(_console(8), "hello world", _opts(8)) == Measurement(5, 8)


def test_text_measure() -> None:
    """Test that Text.__rich_measure__ returns the correct Measurement."""
    assert Text("ab cde").__rich_measure__(_console(), _opts()) == Measurement(3, 6)


def test_table_measure_natural_width() -> None:
    """Test that Table.__rich_measure__ returns the correct Measurement."""
    t = Table("A", "B", box=ASCII)
    t.add_row("1", "2")

    # Widths [1,1], overhead = (ncols+1) + 2*pad*ncols = 3 + 4 = 7 -> max 9
    m = t.__rich_measure__(_console(), _opts())
    assert m.maximum == 9


def test_normalise_orders_bounds() -> None:
    """Test that Measurement.normalise orders bounds correctly."""
    assert Measurement(10, 3).normalise() == Measurement(3, 3)


def test_align_centers_table_via_measurement() -> None:
    """Test that Align.center centers a table via Measurement."""
    t = Table("A", "B", box=ASCII)
    t.add_row("1", "2")  # Natural width 9
    c = _console(30)
    c.print(Align.center(t))
    first = c.file.getvalue().splitlines()[0]
    assert first == " " * 10 + "+---+---+" + " " * 11
