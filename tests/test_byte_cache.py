"""Unit tests for CachedBytes: byte caching of Tables and Panels in Console.print."""

import functools

import pytest

from conftest import ASCII_NAME_AGE_TABLE

from fastrich.box import ASCII
from fastrich.panel import Panel
from fastrich.segment import encode_line, split_lines
from fastrich.style import Style
from fastrich.table import Table


@pytest.fixture
def cc(make_console):
    """Factory for a truecolor console writing to an in-memory buffer."""
    return functools.partial(make_console, color="truecolor")


def _pipeline_bytes(console, renderable) -> bytes:
    """The expected bytes via the existing segment pipeline (no trailing end)."""
    no_color, encoding = console.no_color, console.encoding
    return b"\n".join(
        encode_line(tuple(line), no_color, encoding)
        for line in split_lines(console.render(renderable))
    )


def test_table_bytes_match_pipeline(cc, sample_table) -> None:
    """Cached Table bytes are byte-identical to the segment pipeline."""
    c = cc()
    t = sample_table()
    assert t.__rich_bytes__(c, c.options) == _pipeline_bytes(c, t)


def test_panel_bytes_match_pipeline(cc) -> None:
    """Cached Panel bytes are byte-identical to the segment pipeline."""
    c = cc()
    p = Panel("hello", title="hi", border_style=Style(color="blue"))
    assert p.__rich_bytes__(c, c.options) == _pipeline_bytes(c, p)


def test_nested_panel_table_match_pipeline(cc, sample_table) -> None:
    """A Panel wrapping a Table still renders correctly through the cache."""
    c = cc()
    p = Panel(sample_table())
    assert p.__rich_bytes__(c, c.options) == _pipeline_bytes(c, p)


def test_cache_hit_returns_same_object(cc, sample_table) -> None:
    """A second render with the same context reuses the cached bytes object."""
    c = cc()
    t = sample_table()
    first = t.__rich_bytes__(c, c.options)
    second = t.__rich_bytes__(c, c.options)
    assert first is second


@pytest.mark.parametrize(
    "build, mutate",
    [
        (lambda sample: sample(), lambda t: t.add_row("Carol", "42")),
        (lambda sample: Table("Name", box=ASCII), lambda t: t.add_column("Age")),
        (lambda sample: sample(), lambda t: t.update_cell(0, 0, "Alicia")),
    ],
    ids=["add_row", "add_column", "update_cell"],
)
def test_invalidation_rebuilds_cache(build, mutate, cc, sample_table) -> None:
    """A tracked mutation rebuilds the cache and matches a fresh pipeline render."""
    c = cc()
    t = build(sample_table)
    before = t.__rich_bytes__(c, c.options)
    mutate(t)
    after = t.__rich_bytes__(c, c.options)
    assert after != before
    assert after == _pipeline_bytes(c, t)


def test_update_cell_out_of_range(sample_table) -> None:
    """update_cell() rejects row/column indices outside the table."""
    t = sample_table()
    with pytest.raises(IndexError):
        t.update_cell(5, 0, "x")
    with pytest.raises(IndexError):
        t.update_cell(0, 5, "x")


def test_mark_dirty_forces_rebuild(cc, sample_table) -> None:
    """mark_dirty() drops the cache so out-of-band mutation is picked up."""
    c = cc()
    t = sample_table()
    first = t.__rich_bytes__(c, c.options)
    t.rows.append(["Dan", "7"])  # in-place mutation bypasses add_row
    stale = t.__rich_bytes__(c, c.options)
    assert stale is first  # not tracked: still cached
    t.mark_dirty()
    fresh = t.__rich_bytes__(c, c.options)
    assert fresh == _pipeline_bytes(c, t)
    assert fresh != first


def test_mark_dirty_after_in_place_row_removal(cc, sample_table) -> None:
    """mark_dirty() picks up rows removed directly on `self.rows`."""
    c = cc()
    t = sample_table()
    full = t.__rich_bytes__(c, c.options)
    del t.rows[0]  # in-place removal bypasses the tracked mutators
    t.mark_dirty()
    fresh = t.__rich_bytes__(c, c.options)
    assert fresh == _pipeline_bytes(c, t)
    assert fresh != full


def test_mark_dirty_resyncs_per_row_arrays(cc, sample_table) -> None:
    """mark_dirty() keeps the parallel per-row arrays matched to `self.rows`.

    Regression: an in-place append left ``_row_versions`` short of ``_row_cache``
    (resized by mark_dirty), so the next render indexed it past its end and
    raised IndexError. Both arrays must track the live row count.
    """
    c = cc()
    t = sample_table()
    t.__rich_bytes__(c, c.options)

    t.rows.append(["Dan", "7"])
    t.rows.append(["Eve", "9"])
    t.mark_dirty()
    assert len(t._row_versions) == len(t.rows)
    assert len(t._row_cache) == len(t.rows)
    # Render must not raise and must reflect the appended rows.
    assert t.__rich_bytes__(c, c.options) == _pipeline_bytes(c, t)

    del t.rows[1:]
    t.mark_dirty()
    assert len(t._row_versions) == len(t.rows)
    assert len(t._row_cache) == len(t.rows)
    assert t.__rich_bytes__(c, c.options) == _pipeline_bytes(c, t)


def test_context_sensitivity_width(cc, sample_table) -> None:
    """A new max_width is cached independently and changes the output."""
    c = cc()
    t = sample_table()
    wide = t.__rich_bytes__(c, c.options._replace(max_width=80))
    narrow = t.__rich_bytes__(c, c.options._replace(max_width=12))
    assert wide != narrow

    # Multi-slot LRU cache: both widths stay resident, so re-rendering at the
    # old width is a hit that returns the very same cached bytes object.
    rewide = t.__rich_bytes__(c, c.options._replace(max_width=80))
    assert rewide is wide


def test_print_fast_path_matches_repeated_calls(cc, sample_table) -> None:
    """print() output is stable and correct across repeated calls."""
    t = sample_table()
    c = cc()
    c.print(t)
    first = c.file.getvalue()

    c2 = cc()
    c2.print(t)  # cache is warm from the first console's render context
    second = c2.file.getvalue()
    assert first == second


def test_print_plain_table_matches_legacy_output(make_console, sample_table) -> None:
    """Plain (no-color) print output is unchanged by the byte cache."""
    t = sample_table()
    c = make_console(color=None, width=80)
    c.print(t)
    assert c.file.text == ASCII_NAME_AGE_TABLE
