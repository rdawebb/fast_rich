"""Console: capability detection, the render-protocol boundary, and output."""

from __future__ import annotations

import io
import os
import sys
from functools import cached_property
from typing import Any, Callable, Iterable, NamedTuple

from .segment import Segment, encode_line, split_lines
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
        self.file: Any = file if file is not None else sys.stdout
        self._width = width
        self._force_terminal = force_terminal
        self._color_system_arg = (
            color_system  # "auto" | None | "standard" | "256" | "truecolor"
        )
        # The byte-emitting writer is resolved and cached from sink type on first write
        self._writer: Callable[[bytes], None] | None = None
        # Caches final bytes for single-string print() calls keyed on (text, style_key, sep, end)
        self._print_cache: dict[tuple, bytes] = {}

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

    @cached_property
    def no_color(self) -> bool:
        """Return whether color is disabled for the console.

        Returns:
            True if color is disabled, False otherwise.
        """
        return self.color_system is None

    @cached_property
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
    ) -> Iterable[Segment]:
        """Yield styled segments for any renderable.

        Args:
            renderable: The renderable to render.
            options: The console options to use.

        Yields:
            One `Segment` per styled run of text.
        """
        if isinstance(renderable, Segment):
            yield renderable

        elif isinstance(renderable, Text):
            yield from renderable.__rich_console__(self, options or self.options)

        elif isinstance(renderable, str):
            yield Segment(renderable)

        elif hasattr(renderable, RICH_PROTOCOL):
            opts = options or self.options

            for child in getattr(renderable, RICH_PROTOCOL)(self, opts):
                yield from self.render(child, opts)

        else:
            yield Segment(str(renderable))

    def render_str(self, renderable) -> str:
        """Render the given renderable as a string, applying color policy if enabled.

        Args:
            renderable: The renderable to render.

        Returns:
            The rendered string.
        """
        if self.no_color:
            return "".join(seg.text for seg in self.render(renderable))

        return "".join(
            seg.style.render(seg.text) if seg.style else seg.text
            for seg in self.render(renderable)
        )

    def _resolve_writer(self) -> Callable[[bytes], None]:
        """Build a writer that emits the encoded bytes to the console sink.

        The sink type is inspected once; the returned callable takes raw bytes
        (as produced by `print`) and writes them in the form the sink accepts,
        decoding back to str only for a pure text sink.

        Returns:
            A callable that writes encoded bytes to the sink.
        """
        file = self.file

        # Text stream over a raw byte buffer: emit bytes
        buffer = getattr(file, "buffer", None)
        if buffer is not None:
            buffer_write, buffer_flush = buffer.write, buffer.flush

            def write_via_buffer(data: bytes) -> None:
                """Write bytes via the buffer's write method, then flush.

                Args:
                    data: The bytes to write.
                """
                buffer_write(data)
                buffer_flush()

            return write_via_buffer

        # Native binary sink: emit bytes directly
        if isinstance(file, (io.RawIOBase, io.BufferedIOBase)):
            file_write = file.write
            file_flush = getattr(file, "flush", None)

            def write_binary(data: bytes) -> None:
                """Write binary data directly to the file.

                Args:
                    data: The bytes to write.
                """
                file_write(data)
                if file_flush:
                    file_flush()

            return write_binary

        # Pure text sink (e.g. StringIO): decode bytes back to str
        encoding = self.encoding
        file_write = file.write
        file_flush = getattr(file, "flush", None)

        def write_text(data: bytes) -> None:
            """Write text data to the file, decoding bytes to str using the console encoding.

            Args:
                data: The bytes to write.
            """
            file_write(data.decode(encoding))
            if file_flush:
                file_flush()

        return write_text

    def _write_bytes(self, data: bytes) -> None:
        """Write the encoded bytes to the console sink via the cached writer.

        Args:
            data: The bytes to write.
        """
        if self._writer is None:
            self._writer = self._resolve_writer()

        self._writer(data)

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

        # Fast path: single plain string — cache the final bytes keyed on content + style
        if len(objects) == 1 and isinstance(objects[0], str):
            key = (objects[0], style._key if style is not None else None, sep, end)
            cached = self._print_cache.get(key)

            if cached is None:
                seg = Segment(objects[0], style)
                no_color, encoding = self.no_color, self.encoding
                lines = [
                    encode_line(tuple(line), no_color, encoding)
                    for line in split_lines([seg])
                ]

                cached = b"\n".join(lines) + end.encode(encoding)
                self._print_cache[key] = cached

            self._write_bytes(cached)
            return

        segments = []
        for i, obj in enumerate(objects):
            if i:
                segments.append(Segment(sep))

            if style is not None and isinstance(obj, str):
                segments.append(Segment(obj, style))

            else:
                segments.extend(self.render(obj))

        no_color, encoding = self.no_color, self.encoding

        lines = [
            encode_line(tuple(line), no_color, encoding)
            for line in split_lines(segments)
        ]

        self._write_bytes(b"\n".join(lines) + end.encode(encoding))
