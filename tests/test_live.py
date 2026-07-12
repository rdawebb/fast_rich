"""Unit tests for Live (block-overwrite refresh)."""

import pytest

from fastrich import control as ctl
from fastrich.live import Live


@pytest.fixture
def term(make_console):
    """Factory for a colorless console whose sink is treated as a terminal."""
    return lambda width=20: make_console(width=width, color=None, force_terminal=True)


@pytest.fixture
def pipe(make_console):
    """Factory for a console whose sink is not a terminal."""
    return lambda width=20: make_console(width=width, color=None, force_terminal=False)


@pytest.fixture
def one_row_table(simple_table):
    """Factory for a one-row ASCII table (renders as a 5-line block)."""
    return lambda a, b: simple_table([(a, b)])


class FakeClock:
    """A manually advanced monotonic clock."""

    def __init__(self) -> None:
        """Initialise with a zero time."""
        self.now = 0.0

    def __call__(self) -> float:
        """Return the current time."""
        return self.now


def test_render_bytes_has_no_trailing_newline(pipe, one_row_table) -> None:
    """Test that console.render_bytes returns a block with no trailing newline."""
    c = pipe()
    block = c.render_bytes(one_row_table("1", "2"))
    assert not block.endswith(b"\n")
    assert c.render_bytes("hello") == b"hello"


def test_live_animates_and_reflows_mutation(term, one_row_table) -> None:
    """Test that a terminal Live hides the cursor, redraws, and reflects a mutation."""
    c = term()
    t = one_row_table("1", "2")
    with Live(t, console=c) as live:
        t.update_cell(0, 0, "Z")
        live.refresh()

    out = c.file.getvalue()
    assert out.startswith(ctl.HIDE_CURSOR)  # Cursor hidden on start
    assert ctl.up(4) in out  # 5-line block -> repositioned to its top (line diff)
    assert ctl.ERASE_TO_LINE_END in out  # Changed line rewritten in place
    assert b"Z" in out  # Mutation drawn on refresh
    assert out.endswith(ctl.SHOW_CURSOR)  # Cursor restored on stop


def test_live_non_terminal_writes_final_frame_once(pipe, one_row_table) -> None:
    """Test that a non-terminal sink is not animated: only the last frame, no codes."""
    c = pipe()
    with Live(one_row_table("1", "2"), console=c) as live:
        live.update(one_row_table("9", "9"))

    out = c.file.getvalue()
    assert ctl.HIDE_CURSOR not in out and ctl.SHOW_CURSOR not in out
    assert b"9" in out  # Final frame present
    assert b"1" not in out  # Intermediate frame suppressed


def test_live_transient_erases_on_stop(term, one_row_table) -> None:
    """Test that a transient Live erases the block on stop."""
    c = term()
    with Live(one_row_table("1", "2"), console=c, transient=True):
        pass

    out = c.file.getvalue()
    assert out.endswith(ctl.CR + ctl.up(4) + ctl.ERASE_DOWN + ctl.SHOW_CURSOR)


def test_live_non_transient_leaves_frame(term, one_row_table) -> None:
    """Test that a non-transient Live leaves the frame and moves past it on stop."""
    c = term()
    with Live(one_row_table("1", "2"), console=c):
        pass

    out = c.file.getvalue()
    assert b"1" in out
    assert out.endswith(b"\n" + ctl.SHOW_CURSOR)


def test_update_without_refresh_defers_draw(term, one_row_table) -> None:
    """Test that update(refresh=False) does not draw until refresh is called."""
    c = term()
    live = Live(one_row_table("1", "2"), console=c)
    live.start()
    before = c.file.getvalue()
    live.update(one_row_table("9", "9"), refresh=False)
    assert c.file.getvalue() == before  # No draw yet
    live.refresh()
    assert b"9" in c.file.getvalue()
    live.stop()


def test_live_no_renderable_is_safe(term) -> None:
    """Test that starting/stopping with no renderable does not error."""
    c = term()
    with Live(console=c):
        pass

    out = c.file.getvalue()
    assert out.startswith(ctl.HIDE_CURSOR)
    assert out.endswith(ctl.SHOW_CURSOR)


def test_auto_refresh_thread_lifecycle(term) -> None:
    """Test that auto-refresh spawns a ticker on a terminal and joins it on stop."""
    from fastrich.spinner import Spinner

    c = term()
    live = Live(Spinner("line"), console=c, auto_refresh=True, refresh_per_second=60)
    live.start()
    assert live._thread is not None and live._thread.is_alive()
    live.stop()
    assert live._thread is None


def test_auto_refresh_draws_multiple_frames(term) -> None:
    """Test that the ticker redraws repeatedly (>=1 reposition between frames)."""
    import time

    from fastrich.spinner import Spinner

    c = term()
    with Live(Spinner("line"), console=c, auto_refresh=True, refresh_per_second=60):
        time.sleep(0.15)  # ~9 ticks at 60/s; assert generously below
    out = c.file.getvalue()
    assert out.count(ctl.ERASE_TO_LINE_END) >= 1  # Changed frame was rewritten


def test_no_ticker_on_non_terminal(pipe, one_row_table) -> None:
    """Test that a non-terminal sink never spawns a refresh thread."""
    c = pipe()
    t = one_row_table
    live = Live(t("1", "2"), console=c, auto_refresh=True)
    live.start()
    assert live._thread is None
    live.stop()


def test_auto_refresh_disabled_no_thread(term, one_row_table) -> None:
    """Test that auto_refresh=False draws manually with no background thread."""
    c = term()
    t = one_row_table
    live = Live(t("1", "2"), console=c, auto_refresh=False)
    live.start()
    assert live._thread is None
    live.update(t("9", "9"))
    assert b"9" in c.file.getvalue()
    live.stop()


def test_spinner_frame_advances_with_time() -> None:
    """Test that the spinner selects a different frame as elapsed time grows."""
    from fastrich.spinner import Spinner

    sp = Spinner("line")
    first = "".join(s.text for s in sp._segments_at(0.0))
    later = "".join(s.text for s in sp._segments_at(sp.interval * 1.5))
    assert first != later


def test_progress_context_manager_draws_and_updates(term) -> None:
    """Test that Progress as a context manager draws and reflects advances."""
    from fastrich.progress import BarColumn, Progress, TextColumn

    c = term(width=40)
    with Progress(
        TextColumn("{description}"),
        BarColumn(),
        console=c,
        auto_refresh=False,
    ) as p:
        tid = p.add_task("work", total=10, completed=0)
        p.advance(tid, 5)
        p.refresh()  # auto_refresh=False: draw is explicit
    out = c.file.getvalue()
    assert b"work" in out  # Description drawn
    assert ctl.HIDE_CURSOR in out and ctl.SHOW_CURSOR in out  # Live lifecycle
    assert ctl.ERASE_TO_LINE_END in out  # Redrawn on advance (line diff)


def test_line_diff_skips_unchanged_lines(term, one_row_table) -> None:
    """Test that a same-height refresh rewrites only the changed line."""
    c = term()
    t = one_row_table("1", "2")
    with Live(t, console=c, auto_refresh=False) as live:
        start = len(c.file.getvalue())
        t.update_cell(0, 0, "Z")
        live.refresh()
        frame = c.file.getvalue()[start:]
    assert b"Z" in frame  # Changed cell rewritten
    assert b"| A | B |" not in frame  # Unchanged header line not re-emitted
    assert ctl.ERASE_DOWN not in frame  # No full-block clear on same height


def test_line_diff_falls_back_on_height_change(term, simple_table) -> None:
    """Test that a height change uses full block overwrite, not line diff."""
    c = term()
    with Live(simple_table([("1", "2")]), console=c, auto_refresh=False) as live:
        start = len(c.file.getvalue())
        live.update(simple_table([("1", "2"), ("3", "4")]))
        frame = c.file.getvalue()[start:]
    assert ctl.ERASE_DOWN in frame  # Full overwrite path


def test_clean_progress_skips_render(term) -> None:
    """Test that refreshing an unchanged Progress does not redraw."""
    from fastrich.progress import Progress, TextColumn

    c = term(width=30)
    with Progress(TextColumn("{description}"), console=c, auto_refresh=False) as p:
        p.add_task("task")
        p.refresh()
        start = len(c.file.getvalue())
        p.refresh()  # Nothing changed since the last draw
        p.refresh()
        assert len(c.file.getvalue()) == start  # No bytes written at all


def test_time_based_progress_is_never_clean(term) -> None:
    """Test that a clock-driven column redraws even with no task mutation."""
    from fastrich.progress import Progress, TimeElapsedColumn

    c = term(width=30)
    with Progress(TimeElapsedColumn(), console=c, auto_refresh=False) as p:
        p.add_task("task")
        p.refresh()
        start = len(c.file.getvalue())
        p.refresh()
        assert len(c.file.getvalue()) > start  # Redrawn despite no state change


def test_plain_renderable_always_redraws(term, one_row_table) -> None:
    """Test that a renderable with no dirty protocol is assumed dirty."""
    c = term()
    t = one_row_table("1", "2")
    with Live(t, console=c, auto_refresh=False) as live:
        start = len(c.file.getvalue())
        t.update_cell(0, 0, "Z")  # Mutated in place; Live cannot know
        live.refresh()
        assert b"Z" in c.file.getvalue()[start:]


def test_min_interval_drops_early_refresh(term) -> None:
    """Test that refreshes inside the min_interval floor are dropped."""
    from fastrich.progress import Progress, TextColumn

    c = term(width=30)
    clock = FakeClock()
    p = Progress(
        TextColumn("{description}"),
        console=c,
        auto_refresh=False,
        min_interval=0.1,
        get_time=clock,
    )
    with p:
        tid = p.add_task("task")
        p.refresh()  # First draw, at t=0
        start = len(c.file.getvalue())

        clock.now = 0.05  # Inside the floor
        p.update(tid, description="early")
        p.refresh()
        assert len(c.file.getvalue()) == start  # Dropped

        clock.now = 0.11  # Past the floor
        p.refresh()
        assert b"early" in c.file.getvalue()[start:]  # Deferred state drawn


def test_stop_forces_the_final_frame(term) -> None:
    """Test that a throttled final update still lands, forced on stop."""
    from fastrich.progress import Progress, TextColumn

    c = term(width=30)
    clock = FakeClock()
    p = Progress(
        TextColumn("{description}"),
        console=c,
        auto_refresh=False,
        min_interval=10.0,  # Nothing would draw for 10s
        get_time=clock,
    )
    with p:
        tid = p.add_task("task")
        p.refresh()
        start = len(c.file.getvalue())
        p.update(tid, description="final")
        p.refresh()
        assert len(c.file.getvalue()) == start  # Throttled away

    assert b"final" in c.file.getvalue()[start:]  # Forced through on stop


def test_update_marks_dirty_without_immediate_draw(term) -> None:
    """Test the throttle model: update() alone does not draw (the tick does)."""
    from fastrich.progress import Progress, TextColumn

    c = term(width=30)
    with Progress(TextColumn("{description}"), console=c, auto_refresh=False) as p:
        before = len(c.file.getvalue())
        p.update(p.add_task("task"), description="changed")
        assert len(c.file.getvalue()) == before  # No draw from mutation
        p.refresh()
        assert b"changed" in c.file.getvalue()[before:]  # Explicit refresh draws
