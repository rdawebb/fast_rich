"""Live: a refreshing display region for a single renderable."""

from __future__ import annotations

from threading import Event, RLock, Thread
from time import monotonic
from typing import TYPE_CHECKING, Callable, Literal

from . import control

if TYPE_CHECKING:
    from .console import Console


class Live:
    """A live-updating display region for one renderable."""

    def __init__(
        self,
        renderable=None,
        *,
        console: Console | None = None,
        transient: bool = False,
        auto_refresh: bool = True,
        refresh_per_second: float = 15.0,
        min_interval: float = 0.0,
        get_time: Callable[[], float] = monotonic,
        screen: bool = False,
        vertical_overflow: Literal["crop", "ellipsis", "visible"] = "ellipsis",
    ) -> None:
        """Initialise a Live display.

        Args:
            renderable: The initial renderable to display.
            console: The console to draw on, default Console created if None.
            transient: Erase the display on stop instead of leaving the final
                frame in place.
            auto_refresh: Whether to automatically refresh the display.
            refresh_per_second: The number of times to refresh per second.
            min_interval: Minimum seconds between draws, 0 (default) draws on every refresh.
            get_time: Injectable monotonic clock, for deterministic throttling.
            screen: Render to an alternate screen buffer for the session.
            vertical_oveflow: How to handle a frame taller than the console;
                "crop" (truncate), "ellipsis" (truncate with a marker), or
                "visible" (draw in full).
        """
        if console is None:
            from .console import Console

            console = Console()

        self.console = console
        self._renderable = renderable
        self.transient = transient
        self.screen = screen
        self.vertical_overflow = vertical_overflow
        self.auto_refresh = auto_refresh
        self._interval = 1.0 / refresh_per_second if refresh_per_second > 0 else None
        self._min_interval = min_interval
        self._get_time = get_time
        self._last_draw: float | None = None  # None until the first draw
        self._dirty = True
        self._lines = 0  # Height of the last drawn block
        self._prev_lines: list[bytes] | None = None
        self._started = False
        self._pending: bytes | None = None  # Last frame, for non-terminal sinks
        self._lock = RLock()
        self._stop_event: Event | None = None
        self._thread: Thread | None = None

    def __enter__(self) -> Live:
        """Start the live display on context entry.

        Returns:
            The Live instance.
        """
        self.start()

        return self

    def __exit__(self, *exc) -> None:
        """Stop the live display on context exit.

        Args:
            exc: Exception arguments, if any.
        """
        self.stop()

    def start(self) -> None:
        """Begin the live display, hiding the cursor and drawing the first frame."""
        with self._lock:
            if self._started:
                return

            self._started = True
            if self.screen:
                self.console._write_control(control.ALT_SCREEN_ENTER, control.HOME)
            self.console.show_cursor(False)

            if self._renderable is not None:
                self.refresh()

        if self._auto_refresh_wanted():
            self._stop_event = Event()
            self._thread = Thread(target=self._refresh_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """End the live display, finalising the frame and restoring the cursor."""
        if self._stop_event is not None:
            self._stop_event.set()

        if self._thread is not None:
            self._thread.join()
            self._thread = None
            self._stop_event = None

        with self._lock:
            if not self._started:
                return

            # Throttled/clean-gated refresh drops frames, so the final one has to be forced
            self.refresh(force=True)

            self._started = False

            if not self.console.is_terminal:
                if self._pending is not None:
                    self.console._write_bytes(self._pending + b"\n")

                self.console.show_cursor(True)
                return

            if self.transient and self._lines and not self.screen:
                self.console._write_control(
                    control.CR, control.up(self._lines - 1), control.ERASE_DOWN
                )

            elif self._lines and not self.screen:
                self.console._write_bytes(b"\n")  # Move the cursor past the block

            self.console.show_cursor(True)
            if self.screen:
                self.console._write_control(control.ALT_SCREEN_EXIT)

    def update(self, renderable, *, refresh: bool = True) -> None:
        """Replace the displayed renderable and optionally redraw.

        Args:
            renderable: The new renderable to display.
            refresh: Redraw immediately (default True).
        """
        with self._lock:
            self._renderable = renderable
            self._dirty = True

            if refresh:
                self.refresh()

    def touch(self) -> None:
        """Mark the display as needing a redraw at the next refresh."""
        self._dirty = True

    def _needs_redraw(self) -> bool:
        """Whether the renderable's state differs from the drawn frame.

        A renderable that does not implement `__rich_dirty__` is assumed dirty:
        Live has no way to know it hasn't been mutated in place.

        Returns:
            True if a redraw is needed, False if the drawn frame is current.
        """
        if self._dirty:
            return True

        is_dirty = getattr(self._renderable, "__rich_dirty__", None)

        return True if is_dirty is None else bool(is_dirty())

    def _throttled(self) -> bool:
        """Whether a draw right now would land inside the min_interval floor.

        Returns:
            True if the draw should be dropped, False if it may proceed.
        """
        if not self._min_interval or self._last_draw is None:
            return False

        return self._get_time() - self._last_draw < self._min_interval

    def refresh(self, *, force: bool = False) -> None:
        """Redraw the current renderable, overwriting the previous frame.

        Skipped when the renderable reports itself unchanged, or when the last
        draw was less than `min_interval` ago. A skipped refresh leaves the
        state dirty, so the next unthrottled refresh draws it.

        Args:
            force: Draw even if unchanged or inside the min_interval floor.
                Used for the final frame on stop, which must not be dropped.
        """
        with self._lock:
            if self._renderable is None:
                return

            if not force and (not self._needs_redraw() or self._throttled()):
                return

            self._last_draw = self._get_time()
            self._dirty = False

            mark_clean = getattr(self._renderable, "__rich_clean__", None)
            if mark_clean is not None:
                mark_clean()

            block = self.console.render_bytes(self._renderable)
            new_lines = block.split(b"\n")

            if not self.console.is_terminal:
                self._pending = block  # Drawn once, on stop
                return

            new_lines = self._clip(new_lines)
            block = b"\n".join(new_lines)
            height = len(new_lines)

            if self._prev_lines is not None and len(self._prev_lines) == height:
                self.console._write_bytes(
                    self._diff_bytes(self._prev_lines, new_lines, height)
                )

            else:
                if self._lines:
                    # Return to the top and clear so a shorter/taller new frame draws cleanly
                    self.console._write_control(
                        control.CR, control.up(self._lines - 1), control.ERASE_DOWN
                    )

                self.console._write_bytes(block)

            self._prev_lines = new_lines
            self._lines = height

    def _clip(self, lines: list[bytes]) -> list[bytes]:
        """Clip a frame to the console's height, truncating if necessary.

        Args:
            lines: The frame's per-line bytes.

        Returns:
            The clipped frame's per-line bytes.
        """
        if self.vertical_overflow == "visible":
            return lines

        limit = self.console.height
        if len(lines) <= limit or limit < 1:
            return lines

        clipped = lines[:limit]
        if self.vertical_overflow == "ellipsis":
            clipped[-1] = b"..."

        return clipped

    def _diff_bytes(self, prev: list[bytes], new: list[bytes], height: int) -> bytes:
        """Build the byte sequence that rewrites only the changed lines.

        Walks from the top of the block keeping the cursor at column 0 of each
        row; a changed row is rewritten, an unchanged row is skipped by moving down.
        The cursor ends on the last row for the next refresh.

        Args:
            prev: The previous frame's per-line bytes.
            new: The new frame's per-line bytes.
            height: The (shared) number of lines.

        Returns:
            The encoded control/content byte sequence.
        """
        buf = bytearray()
        buf += control.CR + control.up(height - 1)  # Top row

        for i in range(height):
            changed = new[i] != prev[i]
            if changed:
                buf += new[i]
                buf += control.ERASE_TO_LINE_END

            if i < height - 1:
                # Move to column 0 of the next row
                if changed:
                    buf += control.CR + control.down(1)

                else:
                    buf += control.down(1)

        return bytes(buf)

    def _auto_refresh_wanted(self) -> bool:
        """Whether background refresh thread should run for this session.

        Returns:
            True if auto-refresh is wanted, False otherwise.
        """
        return (
            self.auto_refresh
            and self._interval is not None
            and self.console.is_terminal
        )

    def _refresh_loop(self) -> None:
        """Tick refresh() at the specified interval until stopped."""
        assert self._stop_event is not None
        while not self._stop_event.wait(self._interval):
            self.refresh()
