"""Live: a refreshing display region for a single renderable."""

from __future__ import annotations

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
    ) -> None:
        """Initialise a Live display.

        Args:
            renderable: The initial renderable to display.
            console: The console to draw on, default Console created if None.
            transient: Erase the display on stop instead of leaving the final
                frame in place.
        """
        if console is None:
            from .console import Console

            console = Console()

        self.console = console
        self._renderable = renderable
        self.transient = transient
        self._lines = 0  # Height of the last drawn block
        self._started = False
        self._pending: bytes | None = None  # Last frame, for non-terminal sinks

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
        if self._started:
            return

        self._started = True
        self.console.show_cursor(False)

        if self._renderable is not None:
            self.refresh()

    def stop(self) -> None:
        """End the live display, finalising the frame and restoring the cursor."""
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
        self._renderable = renderable
        if refresh:
            self.refresh()

    def refresh(self) -> None:
        """Redraw the current renderable, overwriting the previous frame."""
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
