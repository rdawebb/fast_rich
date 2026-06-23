"""Width-aware word wrapping.

Operates on a plain string and returns offset ranges, so callers can re-map the
breaks onto styled spans without losing styling. Greedy word packing; words longer
than the width are hard-broken at codepoint boundaries.
"""

from __future__ import annotations

from typing import Iterable

from ._width import cell_len


def fit_end(text: str, width: int) -> int:
    """Largest prefix index of `text` whose width does not exceed `width`.

    Args:
        text: The input string to fit within the width.
        width: The maximum width allowed for the prefix.

    Returns:
        The index of the last character in the prefix that fits within the width.
    """
    total = 0
    for i, ch in enumerate(text):
        cw = cell_len(ch)
        if total + cw > width:
            return i

        total += cw

    return len(text)


def _words(text: str) -> Iterable[tuple[int, int]]:
    """Yield (start, end) for each maximal run of non-space characters.

    Args:
        text: The input string to split into words.

    Yields:
        (start, end) pairs of indices for each maximal run of non-space characters.
    """
    i, n = 0, len(text)
    while i < n:
        if text[i] == " ":
            i += 1
            continue

        j = i
        while j < n and text[j] != " ":
            j += 1

        yield i, j
        i = j


def _hard_break(text: str, start: int, end: int, width: int) -> list[tuple[int, int]]:
    """Break an over-long word [start, end) into chunks each <= width columns.

    Args:
        text: The input string to break.
        start: The starting index of the word to break.
        end: The ending index of the word to break.
        width: The maximum width allowed for each chunk.

    Returns:
        A list of (start, end) pairs representing the chunks of the word.
    """
    chunks = []
    s, w, i = start, 0, start
    while i < end:
        cw = cell_len(text[i])
        if w + cw > width and i > s:
            chunks.append((s, i))
            s, w = i, 0

        w += cw
        i += 1

    chunks.append((s, end))

    return chunks


def wrap_offsets(text: str, width: int) -> list[tuple[int, int]]:
    """Return a list of (start, end) line ranges wrapping `text` to `width`.

    Args:
        text: The input string to wrap.
        width: The maximum width allowed for each line.

    Returns:
        A list of (start, end) pairs representing the line ranges.
    """
    if not text:
        return [(0, 0)]

    if width <= 0:
        return [(0, len(text))]

    lines = []
    cur_s = cur_e = None
    cur_w = 0

    def flush():
        nonlocal cur_s, cur_e, cur_w
        if cur_s is not None and cur_e is not None:
            lines.append((cur_s, cur_e))
            cur_s = cur_e = None
            cur_w = 0

    for ws, we in _words(text):
        wlen = cell_len(text[ws:we])
        if wlen > width:
            flush()
            lines.extend(_hard_break(text, ws, we, width))
            continue

        if cur_s is None:
            cur_s, cur_e, cur_w = ws, we, wlen
        elif cur_w + 1 + wlen <= width:  # +1 for the joining space
            cur_e, cur_w = we, cur_w + 1 + wlen
        else:
            flush()
            cur_s, cur_e, cur_w = ws, we, wlen

    flush()

    return lines or [(0, 0)]
