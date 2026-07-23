"""Width-aware word wrapping.

Operates on a plain string and returns offset ranges, so callers can re-map the
breaks onto styled spans without losing styling. Greedy word packing; words longer
than the width are hard-broken at codepoint boundaries.
"""

from __future__ import annotations

import re
from typing import Iterable

from ._width import cell_len, char_cell_len

# A run of non-spaces (group 1) plus the spaces on either side; the leading
# spaces only ever attach to the first word of a range
_WORD_RE = re.compile(r" *([^ ]+) *")


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
        cw = char_cell_len(ch)
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
        cw = char_cell_len(text[i])
        if w + cw > width and i > s:
            chunks.append((s, i))
            s, w = i, 0

        w += cw
        i += 1

    chunks.append((s, end))

    return chunks


def nofold_offsets(
    text: str, start: int, end: int, width: int, ascii_only: bool | None = None
) -> list[int]:
    """Break offsets for no-fold wrapping of `text[start:end]` to `width`.

    A word is a run of non-spaces plus any spaces to its right; the first word
    also takes leading spaces.

    Args:
        text: The full string (offsets index into it, not into a slice).
        start: The start index of the range to wrap.
        end: The end index of the range to wrap.
        width: The maximum width allowed for each line.
        ascii_only: Whether `text` is all-ASCII.

    Returns:
        Indices within (start, end) at which to break the line.
    """
    if ascii_only is None:
        ascii_only = text.isascii()

    # ASCII width == character count
    if ascii_only and end - start <= width:
        return []

    breaks: list[int] = []
    append = breaks.append
    _cell_len = cell_len
    cell_offset = 0

    for match in _WORD_RE.finditer(text, start, end):
        lead = match.start()
        stripped_end = match.end(1)
        trail_end = match.end()

        # Trailing spaces never merge into the preceding cluster
        word_w = (
            stripped_end - lead if ascii_only else _cell_len(text[lead:stripped_end])
        )
        full_w = word_w + (trail_end - stripped_end)

        if word_w <= width - cell_offset:
            cell_offset += full_w

        else:
            # Reaching here means `cell_offset` is non-zero
            if lead > start:
                append(lead)

            cell_offset = full_w

    return breaks


def wrap_offsets(text: str, width: int) -> list[tuple[int, int]]:
    """Return a list of (start, end) line ranges wrapping `text` to `width`.

    Whitespace at interior wrap points is consumed (shown on neither line), but
    leading whitespace before the first word and trailing whitespace after the
    last word are preserved.

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

    def flush() -> None:
        """Append the current line to `lines` and reset the cursor."""
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

    if not lines:
        # Text is empty or all whitespace, keep as a single line
        return [(0, len(text))]

    # Extend outer ranges to cover boundary whitespace
    lines[0] = (0, lines[0][1])
    lines[-1] = (lines[-1][0], len(text))

    return lines
