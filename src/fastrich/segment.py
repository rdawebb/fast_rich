"""Segment: the main render mode, line splitting, and the line encode cache.

A `Segment` is a run of text with one style. Renderables yield segments; the
Console splits them into lines and encodes each line to bytes. The encode step is
memoised per line, so an unchanged line reuses its bytes instead of re-encoding.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Iterable, NamedTuple, Optional

from ._width import cell_len
from .style import Style


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

    Args:
        line: A list of `Segment` instances representing the line to encode.
        no_color: Whether to disable color rendering.
        encoding: The encoding to use for the output bytes.

    Returns:
        The encoded line as bytes.
    """
    if no_color:
        text = "".join(seg.text for seg in line)

    else:
        text = "".join(
            seg.style.render(seg.text) if seg.style else seg.text for seg in line
        )

    return text.encode(encoding)
