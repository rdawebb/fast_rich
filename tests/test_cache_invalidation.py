"""Cache-invalidation correctness — the gate before Live.

Live re-renders a mutating renderable every frame, so invalidation across the
table render caches must be airtight: the resolve cache (`_resolved`), the
per-row L2 cache (`_row_cache`), and the L1 byte cache (`_byte_cache`). These
tests pin both invalidation paths — documented mutators
(`update_cell`/`add_row`/`add_column`, row-precise) and the coarse out-of-band
path (`mark_dirty` -> `_on_mark_dirty`) — and the render-context keying of L1.
The console single-string print cache is also LRU-bounded here.
"""

import io

from fastrich.align import Align
from fastrich.box import ASCII
from fastrich.columns import Columns
from fastrich.console import _MAX_PRINT_CACHE, Console
from fastrich.panel import Panel
from fastrich.table import Table
from fastrich.text import Text


def _print(renderable, *, width: int = 24, color=None, markup: bool = True) -> str:
    """Render via console.print (exercises the real L1 byte-cache path)."""
    c = Console(
        file=io.StringIO(),
        color_system=color,
        force_terminal=color is not None,
        width=width,
        markup=markup,
    )
    c.print(renderable)
    return c.file.getvalue()


def _table(rows, headers=("A", "B")) -> Table:
    """Build a fresh ASCII table from a sequence of row tuples."""
    t = Table(*headers, box=ASCII)
    for row in rows:
        t.add_row(*row)
    return t


def test_rerender_hits_byte_cache() -> None:
    """Test that an unchanged re-render returns the cached bytes object (L1 hit)."""
    t = _table([("1", "2"), ("3", "4")])
    c = Console(file=io.StringIO(), color_system=None, width=24)
    opts = c.options
    assert t.__rich_bytes__(c, opts) is t.__rich_bytes__(c, opts)


def test_update_cell_matches_fresh() -> None:
    """Test that update_cell yields the same output as a freshly built table."""
    t = _table([("1", "2"), ("3", "4")])
    _print(t)  # Warm all caches
    t.update_cell(0, 1, "X")
    assert _print(t) == _print(_table([("1", "X"), ("3", "4")]))


def test_update_cell_is_row_precise() -> None:
    """Test that update_cell rebuilds only its row's L2 entry, reusing others."""
    t = _table([("1", "2"), ("3", "4"), ("5", "6")])
    c = Console(file=io.StringIO(), color_system=None, width=24)
    opts = c.options
    t.__rich_bytes__(c, opts)  # Populate row cache
    before = list(t._row_cache)
    t.update_cell(1, 0, "Z")  # Same width, no reflow
    t.__rich_bytes__(c, opts)
    after = t._row_cache
    assert after[0] is before[0]  # Untouched rows reuse their line-lists
    assert after[2] is before[2]
    assert after[1] is not before[1]  # Changed row rebuilt


def test_add_row_matches_fresh() -> None:
    """Test that add_row after warming matches a freshly built table."""
    t = _table([("1", "2")])
    _print(t)
    t.add_row("3", "4")
    assert _print(t) == _print(_table([("1", "2"), ("3", "4")]))


def test_add_column_matches_fresh() -> None:
    """Test that add_column after warming matches a freshly built table."""
    t = _table([("1", "2")])
    _print(t)
    t.add_column("C")
    fresh = _table([("1", "2")], headers=("A", "B"))
    fresh.add_column("C")
    assert _print(t) == _print(fresh)


def test_out_of_band_assignment_needs_mark_dirty() -> None:
    """Test that a raw rows[][] assignment is stale until mark_dirty, then fresh."""
    t = _table([("1", "2")])
    warm = _print(t)
    t.rows[0][0] = "ZZ"  # Bypasses update_cell -> not tracked
    assert _print(t) == warm  # Contract: out-of-band needs mark_dirty
    t.mark_dirty()
    assert _print(t) == _print(_table([("ZZ", "2")]))


def test_in_place_text_mutation_needs_mark_dirty() -> None:
    """Test the keystone: a Text cell mutated in place + mark_dirty matches fresh."""
    cell = Text("hi")
    t = _table([(cell, "x")])
    warm = _print(t)
    cell.append("!")  # In-place mutation the Table's caches don't observe
    assert _print(t) == warm  # Table caches still hold the old render
    t.mark_dirty()
    assert _print(t) == _print(_table([(Text("hi!"), "x")]))


def test_mark_dirty_reflows_all_rows() -> None:
    """Test that mark_dirty drops the resolve + all L2 caches, so widths reflow."""
    t = _table([("a", "1"), ("b", "2")])
    _print(t)
    t.rows[0][0] = "wide_value_here"  # Widens column 0 for every row
    t.mark_dirty()
    fresh = _table([("wide_value_here", "1"), ("b", "2")])
    assert _print(t) == _print(fresh)  # Row "b" repadded to the new width


def test_width_context_invalidation() -> None:
    """Test that L1 is keyed per width: distinct widths differ, repeats match."""
    t = _table([("a fairly long cell value", "y")])
    narrow = _print(t, width=16)  # Long cell must crop/wrap here
    wide = _print(t, width=60)  # Fits here
    assert narrow != wide
    assert _print(t, width=16) == narrow  # Re-render at a seen width is correct
    assert _print(t, width=16) == _print(
        _table([("a fairly long cell value", "y")]), width=16
    )


def test_color_context_invalidation() -> None:
    """Test that the color policy is part of the byte-cache key."""
    t = _table([("1", "2")])
    assert _print(t, color=None) != _print(t, color="standard")


def test_markup_context_invalidation() -> None:
    """Test that the markup policy reaches the resolve cache and changes output."""
    t = _table([("[bold]x[/]", "y")])
    on = _print(t, markup=True, color="standard")
    off = _print(t, markup=False, color="standard")
    assert on != off  # markup=False keeps the literal brackets


def test_byte_cache_is_lru_bounded() -> None:
    """Test that the byte cache stays bounded and stays correct after eviction."""
    t = _table([("1", "2")])
    for w in range(10, 30):  # 20 distinct render contexts, no mutation
        _print(t, width=w)
    assert len(t._byte_cache) <= t._max_byte_contexts
    assert _print(t, width=10) == _print(_table([("1", "2")]), width=10)


def test_print_cache_is_lru_bounded() -> None:
    """Test that the single-string print cache stays bounded and stays correct."""
    c = Console(file=io.StringIO(), color_system=None, width=24)
    for i in range(_MAX_PRINT_CACHE + 50):  # Distinct strings overflow the cap
        c.print(f"line {i}")

    assert len(c._print_cache) <= _MAX_PRINT_CACHE

    # An evicted string re-renders correctly against a fresh console
    fresh = Console(file=io.StringIO(), color_system=None, width=24)
    c.print("line 0")  # Evicted earlier
    fresh.print("line 0")
    assert c.file.getvalue().endswith(fresh.file.getvalue())


def test_panel_out_of_band_child_mutation() -> None:
    """Test that a Panel's byte cache invalidates on mark_dirty after a child change."""
    child = Text("hi")
    p = Panel(child, box=ASCII)
    warm = _print(p, width=12)
    child.append("!")
    assert _print(p, width=12) == warm  # Panel byte cache still warm
    p.mark_dirty()
    assert _print(p, width=12) == _print(Panel(Text("hi!"), box=ASCII), width=12)


def test_columns_out_of_band_child_mutation() -> None:
    """Test that Columns' byte cache invalidates on mark_dirty after a child change."""
    child = Text("hi")
    cols = Columns([child, Text("yo")])
    warm = _print(cols, width=20)
    child.append("!")
    assert _print(cols, width=20) == warm  # Columns byte cache still warm
    cols.mark_dirty()
    assert _print(cols, width=20) == _print(
        Columns([Text("hi!"), Text("yo")]), width=20
    )


def test_align_out_of_band_child_mutation() -> None:
    """Test that Align's byte cache invalidates on mark_dirty after a child change."""
    child = Text("hi")
    al = Align(child, "center")
    warm = _print(al, width=20)
    child.append("!")
    assert _print(al, width=20) == warm  # Align byte cache still warm
    al.mark_dirty()
    assert _print(al, width=20) == _print(Align(Text("hi!"), "center"), width=20)
