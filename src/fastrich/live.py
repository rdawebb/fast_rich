"""Live: a refreshing display region for a single renderable."""

from __future__ import annotations

from threading import Event, RLock, Thread
from typing import TYPE_CHECKING

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
    ) -> None:
        """Initialise a Live display.

        Args:
            renderable: The initial renderable to display.
            console: The console to draw on, default Console created if None.
            transient: Erase the display on stop instead of leaving the final
                frame in place.
            auto_refresh: Whether to automatically refresh the display.
            refresh_per_second: The number of times to refresh per second.
        """
        if console is None:
            from .console import Console

            console = Console()

        self.console = console
        self._renderable = renderable
        self.transient = transient
        self.auto_refresh = auto_refresh
        self._interval = 1.0 / refresh_per_second if refresh_per_second > 0 else None
        self._lines = 0  # Height of the last drawn block
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

            self._started = False

            if not self.console.is_terminal:
                if self._pending is not None:
                    self.console._write_bytes(self._pending + b"\n")

                self.console.show_cursor(True)
                return

            if self.transient and self._lines:
                self.console._write_control(
                    control.CR, control.up(self._lines - 1), control.ERASE_DOWN
                )

            elif self._lines:
                self.console._write_bytes(b"\n")  # Move the cursor past the block

            self.console.show_cursor(True)

    def update(self, renderable, *, refresh: bool = True) -> None:
        """Replace the displayed renderable and optionally redraw.

        Args:
            renderable: The new renderable to display.
            refresh: Redraw immediately (default True).
        """
        with self._lock:
            self._renderable = renderable
            if refresh:
                self.refresh()

    def refresh(self) -> None:
        """Redraw the current renderable, overwriting the previous frame."""
        with self._lock:
            if self._renderable is None:
                return

            block = self.console.render_bytes(self._renderable)
            height = block.count(b"\n") + 1

            if not self.console.is_terminal:
                self._pending = block  # Drawn once, on stop
                return

            if self._lines:
                # Return to the top and clear so a shorter/taller new frame draws cleanly
                self.console._write_control(
                    control.CR, control.up(self._lines - 1), control.ERASE_DOWN
                )

            self.console._write_bytes(block)
            self._lines = height

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
