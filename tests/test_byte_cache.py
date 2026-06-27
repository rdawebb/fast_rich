"""Unit tests for CachedBytes: byte caching of Tables and Panels in Console.print."""

import io

from fastrich.box import ASCII
from fastrich.console import Console
from fastrich.panel import Panel
from fastrich.segment import encode_line, split_lines
from fastrich.style import Style
from fastrich.table import Table


def _color_console(width: int = 80) -> Console:
    """A console with color enabled, writing to an in-memory text buffer."""
    return Console(file=io.StringIO(), color_system="truecolor", width=width)


def _pipeline_bytes(console: Console, renderable) -> bytes:
    """The expected bytes via the existing segment pipeline (no trailing end)."""
    no_color, encoding = console.no_color, console.encoding
    return b"\n".join(
        encode_line(tuple(line), no_color, encoding)
        for line in split_lines(console.render(renderable))
    )


def _sample_table() -> Table:
    t = Table("Name", "Age", box=ASCII, border_style=Style(color="red"))
    t.add_row("Alice", "30")
    t.add_row("Bob", "100")
    return t


def test_table_bytes_match_pipeline() -> None:
    """Cached Table bytes are byte-identical to the segment pipeline."""
    c = _color_console()
    t = _sample_table()
    assert t.__rich_bytes__(c, c.options) == _pipeline_bytes(c, t)


def test_panel_bytes_match_pipeline() -> None:
    """Cached Panel bytes are byte-identical to the segment pipeline."""
    c = _color_console()
    p = Panel("hello", title="hi", border_style=Style(color="blue"))
    assert p.__rich_bytes__(c, c.options) == _pipeline_bytes(c, p)


def test_nested_panel_table_match_pipeline() -> None:
    """A Panel wrapping a Table still renders correctly through the cache."""
    c = _color_console()
    p = Panel(_sample_table())
    assert p.__rich_bytes__(c, c.options) == _pipeline_bytes(c, p)


def test_cache_hit_returns_same_object() -> None:
    """A second render with the same context reuses the cached bytes object."""
    c = _color_console()
    t = _sample_table()
    first = t.__rich_bytes__(c, c.options)
    second = t.__rich_bytes__(c, c.options)
    assert first is second


def test_invalidation_on_add_row() -> None:
    """Adding a row rebuilds the cache and changes the output."""
    c = _color_console()
    t = _sample_table()
    before = t.__rich_bytes__(c, c.options)
    t.add_row("Carol", "42")
    after = t.__rich_bytes__(c, c.options)
    assert after != before
    assert after == _pipeline_bytes(c, t)


def test_invalidation_on_add_column() -> None:
    """Adding a column rebuilds the cache."""
    c = _color_console()
    t = Table("Name", box=ASCII)
    before = t.__rich_bytes__(c, c.options)
    t.add_column("Age")
    after = t.__rich_bytes__(c, c.options)
    assert after != before
    assert after == _pipeline_bytes(c, t)


def test_invalidation_on_update_cell() -> None:
    """update_cell() rebuilds the cache and reflects the new value."""
    c = _color_console()
    t = _sample_table()
    before = t.__rich_bytes__(c, c.options)
    t.update_cell(0, 0, "Alicia")
    after = t.__rich_bytes__(c, c.options)
    assert after != before
    assert after == _pipeline_bytes(c, t)


def test_update_cell_out_of_range() -> None:
    """update_cell() rejects row/column indices outside the table."""
    import pytest

    t = _sample_table()
    with pytest.raises(IndexError):
        t.update_cell(5, 0, "x")
    with pytest.raises(IndexError):
        t.update_cell(0, 5, "x")


def test_mark_dirty_forces_rebuild() -> None:
    """mark_dirty() drops the cache so out-of-band mutation is picked up."""
    c = _color_console()
    t = _sample_table()
    first = t.__rich_bytes__(c, c.options)
    t.rows.append(["Dan", "7"])  # in-place mutation bypasses add_row
    stale = t.__rich_bytes__(c, c.options)
    assert stale is first  # not tracked: still cached
    t.mark_dirty()
    fresh = t.__rich_bytes__(c, c.options)
    assert fresh == _pipeline_bytes(c, t)
    assert fresh != first


def test_context_sensitivity_width() -> None:
    """A new max_width is cached independently and changes the output."""
    c = _color_console()
    t = _sample_table()
    wide = t.__rich_bytes__(c, c.options._replace(max_width=80))
    narrow = t.__rich_bytes__(c, c.options._replace(max_width=12))
    assert wide != narrow

    # Multi-slot LRU cache: both widths stay resident, so re-rendering at the
    # old width is a hit that returns the very same cached bytes object.
    rewide = t.__rich_bytes__(c, c.options._replace(max_width=80))
    assert rewide is wide


def test_print_fast_path_matches_repeated_calls() -> None:
    """print() output is stable and correct across repeated calls."""
    t = _sample_table()
    c = _color_console()
    c.print(t)
    first = c.file.getvalue()

    c2 = _color_console()
    c2.print(t)  # cache is warm from the first console's render context
    second = c2.file.getvalue()
    assert first == second


def test_print_plain_table_matches_legacy_output() -> None:
    """Plain (no-color) print output is unchanged by the byte cache."""
    t = _sample_table()
    c = Console(file=io.StringIO(), color_system=None, width=80)
    c.print(t)
    expected = (
        "+-------+-----+\n"
        "| Name  | Age |\n"
        "+-------+-----+\n"
        "| Alice | 30  |\n"
        "| Bob   | 100 |\n"
        "+-------+-----+\n"
    )
    assert c.file.getvalue() == expected
