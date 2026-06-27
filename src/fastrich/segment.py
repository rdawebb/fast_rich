"""Segment: the main render mode, line splitting, and the line encode cache.

A `Segment` is a run of text with one style. Renderables yield segments; the
Console splits them into lines and encodes each line to bytes. The encode step is
memoised per line, so an unchanged line reuses its bytes instead of re-encoding.
"""

from __future__ import annotations

from collections import OrderedDict
from functools import lru_cache
from typing import TYPE_CHECKING, Iterable, NamedTuple, Optional

from ._width import cell_len
from .style import Style

if TYPE_CHECKING:
    from .console import Console, ConsoleOptions


class Segment(NamedTuple):
    """A run of text with one style."""

    text: str
    style: Optional[Style] = None

    @property
    def cell_len(self) -> int:
        """The number of terminal columns this segment occupies.

        Returns:
            The number of terminal columns this segment occupies.
        """
        return cell_len(self.text)


def split_lines(segments) -> Iterable[list[Segment]]:
    """Split an iterable of segments into lines on embedded newlines.

    Yields one `list[Segment]` per line. A trailing newline yields a final
    empty line, mirroring `str.split` semantics.

    Args:
        segments: An iterable of `Segment` instances to split into lines.

    Yields:
        One `list[Segment]` per line.
    """
    line = []
    for seg in segments:
        if "\n" not in seg.text:
            if seg.text:
                line.append(seg)

            continue

        parts = seg.text.split("\n")
        for part in parts[:-1]:
            if part:
                line.append(Segment(part, seg.style))

            yield line

            line = []
        if parts[-1]:
            line.append(Segment(parts[-1], seg.style))

    yield line


@lru_cache(maxsize=8192)
def encode_line(line: list[Segment], no_color: bool, encoding: str) -> bytes:
    """Encode one line (a tuple of Segments) to bytes, applying color policy.

    Memoised on (line, no_color, encoding): identical lines reuse their bytes.
    Adjacent segments with equal style are coalesced into a single run.

    Args:
        line: A list of `Segment` instances representing the line to encode.
        no_color: Whether to disable color rendering.
        encoding: The encoding to use for the output bytes.

    Returns:
        The encoded line as bytes.
    """
    if no_color:
        return "".join(seg.text for seg in line).encode(encoding)

    out = bytearray()
    n = len(line)
    i = 0
    while i < n:
        style = line[i].style
        j = i + 1
        parts = [line[i].text]

        while j < n and line[j].style == style:
            parts.append(line[j].text)
            j += 1

        text = "".join(parts)
        out += style.render_bytes(text, encoding) if style else text.encode(encoding)
        i = j

    return bytes(out)


class CachedBytes:
    """Mixin: memoise a renderable's final encoded bytes, keyed by render context.

    Invalidation is by an explicit `_dirty` flag. Subclasses flip it in their
    documented mutators, out-of-band changes (in-place list mutation, attribute
    reassignment, or a nested mutable child changing) are not tracked and need a
    manual `mark_dirty()` call.
    """

    _dirty: bool
    _max_byte_contexts: int = 8

    if TYPE_CHECKING:

        def __rich_console__(
            self, console: Console, options: ConsoleOptions
        ) -> Iterable[Segment]:
            """Subclasses must yield the Segments for this renderable."""
            ...

    def _init_byte_cache(self) -> None:
        """Initialise the dirty flag and byte cache, call from `__init__`."""
        self._dirty = True
        self._byte_cache = OrderedDict()

    def mark_dirty(self) -> None:
        """Invalidate the cached bytes and subclass-derived caches, call after
        out-of-band mutation."""
        self._dirty = True
        self._on_mark_dirty()

    def _on_mark_dirty(self) -> None:
        """Hook for subclasses to drop caches derived beyond `_byte_cache`."""
        pass

    def __rich_bytes__(self, console: Console, options: ConsoleOptions) -> bytes:
        """Return the encoded bytes for this renderable, without a trailing end.

        Args:
            console: The console to render to.
            options: The console options for this render.

        Returns:
            The rendered bytes, memoised per render context.
        """
        if self._dirty:
            self._byte_cache.clear()
            self._dirty = False

        no_color, encoding = console.no_color, console.encoding
        key = (options.max_width, no_color, encoding, console._markup)
        cache = self._byte_cache

        cached = cache.get(key)
        if cached is not None:
            cache.move_to_end(key)
            return cached

        cached = b"\n".join(
            encode_line(tuple(line), no_color, encoding)
            for line in split_lines(self.__rich_console__(console, options))
        )
        cache[key] = cached
        if len(cache) > self._max_byte_contexts:
            cache.popitem(last=False)

        return cached
