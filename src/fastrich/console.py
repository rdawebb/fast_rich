"""Console: capability detection, the render-protocol boundary, and output."""

from __future__ import annotations

import os
import sys
from typing import Any, Iterable, NamedTuple

from .style import Style
from .text import Text

# A renderable is anything implementing this method, it returns an iterable of
# child renderables (str / Text / nested renderables).
RICH_PROTOCOL = "__rich_console__"


class ConsoleOptions(NamedTuple):
    """Options for the Console."""

    max_width: int


class Console:
    """The Console class provides methods for rendering rich text to the terminal."""

    def __init__(
        self,
        *,
        file: Any | None = None,
        width: int | None = None,
        color_system: str | None = "auto",
        force_terminal: bool | None = None,
    ) -> None:
        """Initialise the Console with optional file, width, color system, and force terminal settings.

        Args:
            file: The file-like object to write output to. Defaults to sys.stdout.
            width: The width of the terminal. Defaults to the terminal width.
            color_system: The color system to use. Defaults to "auto".
            force_terminal: Whether to force the use of a terminal. Defaults to None.
        """
        self.file = file if file is not None else sys.stdout
        self._width = width
        self._force_terminal = force_terminal
        self._color_system_arg = (
            color_system  # "auto" | None | "standard" | "256" | "truecolor"
        )

    def _fileno(self) -> int | None:
        """Return the file descriptor of the console file, or None if not available.

        Returns:
            The file descriptor of the console file, or None if not available.
        """
        try:
            return self.file.fileno()

        except (AttributeError, OSError, ValueError):
            return None

    @property
    def size(self) -> tuple[int, int]:
        """Return the size of the console as (width, height).

        Returns:
            The size of the console as (width, height).
        """
        if self._width is not None:
            return self._width, 25

        cols = os.environ.get("COLUMNS")
        if cols and cols.isdigit():
            return int(cols), 25

        fd = self._fileno()
        if fd is None and sys.__stdout__ is not None:
            fd = sys.__stdout__.fileno()
        if fd is None:
            return 80, 25

        try:
            ts = os.get_terminal_size(fd)
            return ts.columns, ts.lines

        except (OSError, ValueError):
            return 80, 25

    @property
    def width(self) -> int:
        """Return the width of the console.

        Returns:
            The width of the console.
        """
        return self.size[0]

    @property
    def is_terminal(self) -> bool:
        """Return whether the console is a terminal.

        Returns:
            True if the console is a terminal, False otherwise.
        """
        if self._force_terminal is not None:
            return self._force_terminal

        if "FORCE_COLOR" in os.environ:
            return True

        isatty = getattr(self.file, "isatty", None)
        try:
            return bool(isatty()) if isatty else False

        except (OSError, ValueError):
            return False

    @property
    def color_system(self) -> str | None:
        """Return the color system of the console.

        Returns:
            The color system of the console.
        """
        if self._color_system_arg != "auto":
            return self._color_system_arg  # Explicit, incl. forced None

        if "NO_COLOR" in os.environ:
            return None

        force = "FORCE_COLOR" in os.environ
        if not self.is_terminal and not force:
            return None

        colorterm = os.environ.get("COLORTERM", "").lower()
        if "truecolor" in colorterm or "24bit" in colorterm:
            return "truecolor"

        if "256" in os.environ.get("TERM", ""):
            return "256"

        return "standard"

    @property
    def no_color(self) -> bool:
        """Return whether color is disabled for the console.

        Returns:
            True if color is disabled, False otherwise.
        """
        return self.color_system is None

    @property
    def encoding(self) -> str:
        """Return the encoding of the console file.

        Returns:
            The encoding of the console file, defaulting to "utf-8".
        """
        return getattr(self.file, "encoding", None) or "utf-8"

    @property
    def options(self) -> ConsoleOptions:
        """Return the console options.

        Returns:
            The console options.
        """
        return ConsoleOptions(max_width=self.width)

    def _render_text(self, text: Text) -> str:
        """Apply the color policy: plain when disabled, ANSI otherwise.

        Args:
            text: The text to render.

        Returns:
            The rendered text.
        """
        return text.plain if self.no_color else text.render()

    def render(
        self, renderable, options: ConsoleOptions | None = None
    ) -> Iterable[str]:
        """Yield ANSI string pieces for any renderable, color policy applied.

        Args:
            renderable: The renderable to render.
            options: The console options to use.

        Returns:
            The rendered string.
        """
        if isinstance(renderable, Text):
            yield self._render_text(renderable)

        elif isinstance(renderable, str):
            yield self._render_text(Text(renderable))

        elif hasattr(renderable, RICH_PROTOCOL):
            opts = options or self.options

            for child in getattr(renderable, RICH_PROTOCOL)(self, opts):
                yield from self.render(child, opts)

        else:
            yield self._render_text(Text(str(renderable)))

    def render_str(self, renderable) -> str:
        """Render the given renderable as a string, applying color policy if enabled.

        Args:
            renderable: The renderable to render.

        Returns:
            The rendered string.
        """
        return "".join(self.render(renderable))

    def _write(self, s: str) -> None:
        """Write the given string to the console file, applying the encoding if necessary.

        Args:
            s: The string to write.
        """
        buffer = getattr(self.file, "buffer", None)
        if buffer is not None:
            buffer.write(s.encode(self.encoding))
            buffer.flush()

        else:
            self.file.write(s)
            flush = getattr(self.file, "flush", None)
            if flush:
                flush()

    def print(
        self,
        *objects,
        sep: str = " ",
        end: str = "\n",
        style: str | Style | None = None,
    ) -> None:
        """Print the given objects to the console, applying the given style if provided.

        Args:
            objects: The objects to print.
            sep: The separator between objects.
            end: The end-of-line character.
            style: The style to apply to the objects.
        """
        if style is not None and not isinstance(style, Style):
            style = Style.parse(style)

        parts = []
        for obj in objects:
            if style is not None and isinstance(obj, str):
                parts.append(self._render_text(Text(obj, style=style)))

            else:
                parts.append(self.render_str(obj))

        self._write(sep.join(parts) + end)
