"""Console: capability detection, the render-protocol boundary, and output."""

from __future__ import annotations

import io
import os
import sys
from collections import OrderedDict
from contextlib import contextmanager
from functools import cached_property
from typing import TYPE_CHECKING, Any, Callable, Iterable, NamedTuple, Sequence

if TYPE_CHECKING:
    from .theme import Theme

from . import control
from .segment import Segment, encode_line, lru_set, split_lines
from .style import Style
from .text import Text

# A renderable is anything implementing this method, it returns an iterable of
# child renderables (str / Text / nested renderables)
RICH_PROTOCOL = "__rich_console__"

# A byte-cacheable renderable implements this method, returning its final
# encoded bytes (without a trailing end) memoised per render context
BYTES_PROTOCOL = "__rich_bytes__"

# Upper bound on the single-string print() cache, evicted LRU, bounds memory
# under long Live/loop sessions
_MAX_PRINT_CACHE = 1024

# Pre-encoded print() line terminators
_COMMON_ENDS = {"\n": b"\n", "": b""}


def _encode_end(end: str, encoding: str) -> bytes:
    """Return the encoded print() terminator, without re-encoding common cases.

    Args:
        end: The print() terminator string.
        encoding: The encoding to use for the terminator.

    Returns:
        The encoded terminator bytes.
    """
    encoded = _COMMON_ENDS.get(end)

    return encoded if encoded is not None else end.encode(encoding)


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
        markup: bool = True,
        emoji: bool = True,
        theme: Theme | None = None,
    ) -> None:
        """Initialise the Console with optional file, width, color system, and force terminal settings.

        Args:
            file: The file-like object to write output to. Defaults to sys.stdout.
            width: The width of the terminal. Defaults to the terminal width.
            color_system: The color system to use. Defaults to "auto".
            force_terminal: Whether to force the use of a terminal. Defaults to None.
            markup: Whether to parse console markup in strings. Defaults to True.
            emoji: Whether to replace emoji :shortcodes: in strings. Defaults to True.
        """
        self.file: Any = file if file is not None else sys.stdout
        self._width = width
        self._force_terminal = force_terminal
        self._markup = markup
        self._emoji = emoji
        self._theme = theme
        self._color_system_arg = (
            color_system  # "auto" | None | "standard" | "256" | "truecolor"
        )
        # The byte-emitting writer is resolved and cached from sink type on first write
        self._writer: Callable[[bytes], None] | None = None
        # Caches final bytes for single-string print() calls keyed on (text, style_key, sep, end).
        self._print_cache: OrderedDict[tuple, bytes] = OrderedDict()

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

    def _str_to_text(
        self,
        text: str,
        style: Style | None = None,
        markup: bool | None = None,
    ) -> Text:
        """Convert a string to a Text, parsing console markup unless disabled.

        The single place strings become renderables, so markup is applied
        uniformly to top-level `print` arguments and nested string children.

        Args:
            text: The string to convert.
            style: Base style applied under any markup spans.
            markup: Per-call override for markup parsing; falls back to the
                console default when None.

        Returns:
            The resulting Text.
        """
        use_markup = self._markup if markup is None else markup
        emoji_replace = self._emoji_replace if self._emoji else None

        if use_markup and "[" in text:
            from .markup import render as render_markup

            return render_markup(
                text,
                style,
                emoji_replace=emoji_replace,
                style_resolver=self._resolve_style,
            )

        if emoji_replace is not None:
            text = emoji_replace(text)

        return Text(text, style)

    def _emoji_replace(self, text: str) -> str:
        """Substitute :shortcode: emoji in `text` (the markup emoji hook).

        Args:
            text: The text to scan for shortcodes.

        Returns:
            The text with recognised shortcodes replaced by glyphs.
        """
        from .emoji import replace

        return replace(text)

    def resolve_style(self, value: str | Style | None) -> Style | None:
        """Resolve a style param (None, a Style, or a str) to a Style or None.

        A str is resolved theme-first then parsed (see `_resolve_style`), a Style
        passes through, None stays None.

        Args:
            value: None, a Style, or a style name/definition string.

        Returns:
            The resolved Style, or None.
        """
        if value is None or isinstance(value, Style):
            return value

        return self._resolve_style(value)

    def _resolve_style(self, definition: str) -> Style:
        """Resolve a markup tag or base style string to a Style.

        Looks the name up in the active theme first (when set), then falls back
        to parsing it as a style definition. This is the `style_resolver` the
        console hands to the markup parser.

        Args:
            definition: A theme style name or a style definition string.

        Returns:
            The resolved Style.
        """
        if self._theme is not None:
            named = self._theme.get(definition)

            if named is not None:
                return named

        return Style.parse(definition)

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
            yield from self._str_to_text(renderable).__rich_console__(
                self, options or self.options
            )

        elif hasattr(renderable, RICH_PROTOCOL):
            opts = options or self.options

            for child in getattr(renderable, RICH_PROTOCOL)(self, opts):
                yield from self.render(child, opts)

        else:
            yield Segment(str(renderable))

    def render_lines(
        self, renderable, options: ConsoleOptions | None = None
    ) -> list[Sequence[Segment]]:
        """Return a renderable's output as physical lines.

        Args:
            renderable: The renderable to render.
            options: The console options to use.

        Returns:
            A list of lists of segments, where each inner list represents a line.
        """
        opts = options or self.options
        fn = getattr(renderable, "__rich_lines__", None)
        if fn is not None:
            return fn(self, opts)  # Cached list-of-lists, no copy

        return list(split_lines(self.render(renderable, opts)))

    def render_bytes(self, renderable, options: ConsoleOptions | None = None) -> bytes:
        """Render a renderable to its encoded bytes, without a trailing newline.

        Args:
            renderable: The renderable to render.
            options: The console options to use.

        Returns:
            The encoded block bytes (lines joined by newline, no trailing end).
        """
        opts = options or self.options
        if hasattr(renderable, BYTES_PROTOCOL):
            return renderable.__rich_bytes__(self, opts)

        no_color, encoding = self.no_color, self.encoding

        return b"\n".join(
            encode_line(tuple(line), no_color, encoding)
            for line in self.render_lines(renderable, opts)
        )

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

    def _write_control(self, *codes: bytes) -> None:
        """Write terminal control sequences, suppressed when not a terminal.

        Control codes are ASCII `bytes` (from the control module), so they emit
        directly with no per-call encode.

        Args:
            codes: Control sequences to emit in order.
        """
        if not self.is_terminal or not codes:
            return

        return self._write_bytes(b"".join(codes))

    def show_cursor(self, show: bool = True) -> None:
        """Show or hide the terminal cursor.

        Args:
            show: True to show the cursor, False to hide it.
        """
        self._write_control(control.SHOW_CURSOR if show else control.HIDE_CURSOR)

    @contextmanager
    def screen(self):
        """Enter the alternate screen buffer for the duration of the context.

        Hides the cursor and switches to the alternate buffer on entry, restores
        the cursor and the primary buffer on exit. A no-op on non-terminal sinks.

        Yields:
            The console, for use within the block.
        """
        self._write_control(control.ALT_SCREEN_ENTER, control.HIDE_CURSOR, control.HOME)

        try:
            yield self

        finally:
            self._write_control(control.SHOW_CURSOR, control.ALT_SCREEN_EXIT)

    def print(
        self,
        *objects,
        sep: str = " ",
        end: str = "\n",
        style: str | Style | None = None,
        markup: bool | None = None,
    ) -> None:
        """Print the given objects to the console, applying the given style if provided.

        Args:
            objects: The objects to print.
            sep: The separator between objects.
            end: The end-of-line character.
            style: The style to apply to the objects.
            markup: Per-call override for markup parsing; falls back to the
                console default when None.
        """
        if style is not None and not isinstance(style, Style):
            style = self._resolve_style(style)

        # Fast path: single string
        if len(objects) == 1 and isinstance(objects[0], str):
            text = objects[0]
            use_markup = self._markup if markup is None else markup
            key = (
                text,
                style._key if style is not None else None,
                sep,
                end,
                use_markup,
            )
            cache = self._print_cache
            cached = cache.get(key)

            if cached is not None:
                cache.move_to_end(key)

            else:
                if use_markup and "[" in text:
                    segs = list(self._str_to_text(text, style)._segments())
                else:
                    plain = self._emoji_replace(text) if self._emoji else text
                    segs = [Segment(plain, style)]

                no_color, encoding = self.no_color, self.encoding
                lines = [
                    encode_line(line, no_color, encoding) for line in split_lines(segs)
                ]

                cached = b"\n".join(lines) + _encode_end(end, encoding)
                lru_set(cache, key, cached, _MAX_PRINT_CACHE)

            self._write_bytes(cached)
            return

        # Fast path: single byte-cacheable renderable
        if len(objects) == 1 and hasattr(objects[0], BYTES_PROTOCOL):
            body = objects[0].__rich_bytes__(self, self.options)
            self._write_bytes(body + _encode_end(end, self.encoding))
            return

        # Fast path: single line-renderable renderable
        if len(objects) == 1 and hasattr(objects[0], "__rich_lines__"):
            no_color, encoding = self.no_color, self.encoding
            lines = [
                encode_line(tuple(line), no_color, encoding)
                for line in self.render_lines(objects[0])
            ]
            self._write_bytes(b"\n".join(lines) + _encode_end(end, encoding))
            return

        segments = []
        for i, obj in enumerate(objects):
            if i:
                segments.append(Segment(sep))

            if isinstance(obj, str):
                segments.extend(self._str_to_text(obj, style, markup)._segments())

            else:
                segments.extend(self.render(obj))

        no_color, encoding = self.no_color, self.encoding

        lines = [
            encode_line(line, no_color, encoding) for line in split_lines(segments)
        ]

        self._write_bytes(b"\n".join(lines) + _encode_end(end, encoding))
