"""Unit tests for cache-invalidation correctness"""

import functools

import pytest

from fastrich.align import Align
from fastrich.box import ASCII
from fastrich.columns import Columns
from fastrich.console import _MAX_PRINT_CACHE
from fastrich.panel import Panel
from fastrich.text import Text


@pytest.fixture
def pr(render):
    """Render via console.print at this module's default width of 24."""
    return functools.partial(render, width=24)


def test_rerender_hits_byte_cache(make_console, simple_table) -> None:
    """Test that an unchanged re-render returns the cached bytes object (L1 hit)."""
    t = simple_table([("1", "2"), ("3", "4")])
    c = make_console(width=24)
    opts = c.options
    assert t.__rich_bytes__(c, opts) is t.__rich_bytes__(c, opts)


def test_update_cell_matches_fresh(pr, simple_table) -> None:
    """Test that update_cell yields the same output as a freshly built table."""
    t = simple_table([("1", "2"), ("3", "4")])
    pr(t)  # Warm all caches
    t.update_cell(0, 1, "X")
    assert pr(t) == pr(simple_table([("1", "X"), ("3", "4")]))


def test_update_cell_is_row_precise(make_console, simple_table) -> None:
    """Test that update_cell rebuilds only its row's L2 entry, reusing others."""
    t = simple_table([("1", "2"), ("3", "4"), ("5", "6")])
    c = make_console(width=24)
    opts = c.options
    t.__rich_bytes__(c, opts)  # Populate row cache
    before = list(t._row_cache)
    t.update_cell(1, 0, "Z")  # Same width, no reflow
    t.__rich_bytes__(c, opts)
    after = t._row_cache
    assert after[0] is before[0]  # Untouched rows reuse their line-lists
    assert after[2] is before[2]
    assert after[1] is not before[1]  # Changed row rebuilt


def test_add_row_matches_fresh(pr, simple_table) -> None:
    """Test that add_row after warming matches a freshly built table."""
    t = simple_table([("1", "2")])
    pr(t)
    t.add_row("3", "4")
    assert pr(t) == pr(simple_table([("1", "2"), ("3", "4")]))


def test_add_column_matches_fresh(pr, simple_table) -> None:
    """Test that add_column after warming matches a freshly built table."""
    t = simple_table([("1", "2")])
    pr(t)
    t.add_column("C")
    fresh = simple_table([("1", "2")], headers=("A", "B"))
    fresh.add_column("C")
    assert pr(t) == pr(fresh)


def test_out_of_band_assignment_needs_mark_dirty(pr, simple_table) -> None:
    """Test that a raw rows[][] assignment is stale until mark_dirty, then fresh."""
    t = simple_table([("1", "2")])
    warm = pr(t)
    t.rows[0][0] = "ZZ"  # Bypasses update_cell -> not tracked
    assert pr(t) == warm  # Contract: out-of-band needs mark_dirty
    t.mark_dirty()
    assert pr(t) == pr(simple_table([("ZZ", "2")]))


def test_in_place_text_mutation_needs_mark_dirty(pr, simple_table) -> None:
    """Test the keystone: a Text cell mutated in place + mark_dirty matches fresh."""
    cell = Text("hi")
    t = simple_table([(cell, "x")])
    warm = pr(t)
    cell.append("!")  # In-place mutation the Table's caches don't observe
    assert pr(t) == warm  # Table caches still hold the old render
    t.mark_dirty()
    assert pr(t) == pr(simple_table([(Text("hi!"), "x")]))


def test_mark_dirty_reflows_all_rows(pr, simple_table) -> None:
    """Test that mark_dirty drops the resolve + all L2 caches, so widths reflow."""
    t = simple_table([("a", "1"), ("b", "2")])
    pr(t)
    t.rows[0][0] = "wide_value_here"  # Widens column 0 for every row
    t.mark_dirty()
    fresh = simple_table([("wide_value_here", "1"), ("b", "2")])
    assert pr(t) == pr(fresh)  # Row "b" repadded to the new width


def test_width_context_invalidation(pr, simple_table) -> None:
    """Test that L1 is keyed per width: distinct widths differ, repeats match."""
    t = simple_table([("a fairly long cell value", "y")])
    narrow = pr(t, width=16)  # Long cell must crop/wrap here
    wide = pr(t, width=60)  # Fits here
    assert narrow != wide
    assert pr(t, width=16) == narrow  # Re-render at a seen width is correct
    assert pr(t, width=16) == pr(
        simple_table([("a fairly long cell value", "y")]), width=16
    )


def test_color_context_invalidation(pr, simple_table) -> None:
    """Test that the color policy is part of the byte-cache key."""
    t = simple_table([("1", "2")])
    assert pr(t, color=None) != pr(t, color="standard")


def test_markup_context_invalidation(pr, simple_table) -> None:
    """Test that the markup policy reaches the resolve cache and changes output."""
    t = simple_table([("[bold]x[/]", "y")])
    on = pr(t, markup=True, color="standard")
    off = pr(t, markup=False, color="standard")
    assert on != off  # markup=False keeps the literal brackets


def test_byte_cache_is_lru_bounded(pr, simple_table) -> None:
    """Test that the byte cache stays bounded and stays correct after eviction."""
    t = simple_table([("1", "2")])
    for w in range(10, 30):  # 20 distinct render contexts, no mutation
        pr(t, width=w)
    assert len(t._byte_cache) <= t._max_byte_contexts
    assert pr(t, width=10) == pr(simple_table([("1", "2")]), width=10)


def test_print_cache_is_lru_bounded(make_console) -> None:
    """Test that the single-string print cache stays bounded and stays correct."""
    c = make_console(width=24)
    for i in range(_MAX_PRINT_CACHE + 50):  # Distinct strings overflow the cap
        c.print(f"line {i}")

    assert len(c._print_cache) <= _MAX_PRINT_CACHE

    # An evicted string re-renders correctly against a fresh console
    fresh = make_console(width=24)
    c.print("line 0")  # Evicted earlier
    fresh.print("line 0")
    assert c.file.getvalue().endswith(fresh.file.getvalue())


@pytest.mark.parametrize(
    "factory, width",
    [
        (lambda child: Panel(child, box=ASCII), 12),
        (lambda child: Columns([child, Text("yo")]), 20),
        (lambda child: Align(child, "center"), 20),
    ],
    ids=["panel", "columns", "align"],
)
def test_container_out_of_band_child_mutation(pr, factory, width) -> None:
    """Test that a container's byte cache invalidates on mark_dirty after a child change."""
    child = Text("hi")
    container = factory(child)
    warm = pr(container, width=width)
    child.append("!")
    assert pr(container, width=width) == warm  # Byte cache still warm
    container.mark_dirty()
    assert pr(container, width=width) == pr(factory(Text("hi!")), width=width)
