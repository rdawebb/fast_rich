"""Width measurement module - Tier 1/2/3 dispatch.

This module is the reference implementation behind the public `cell_len` /
`char_width` boundary. A Rust implementation (`_width_rs`) may replace it
later without touching callers.

Input is printable text: no control characters, tabs, or escape sequences.
`cell_len` returns the number of terminal columns the string occupies.

Tier 1  ASCII fast path           -> len(), single C-level scan.
Tier 2  per-codepoint summation   -> exact for CJK, combining marks, and
                                     standalone wide emoji.
Tier 3  cluster segmentation      -> only when ZWJ / regional indicators /
                                     variation selectors / emoji modifiers are
                                     present; fixes over-counting of composed
                                     emoji sequences.
"""

from bisect import bisect_right
from functools import lru_cache
from typing import Optional, Sequence, TypeVar

from ._width_table import AMBIGUOUS_RANGES, UNICODE_VERSION, WIDTH_RANGES

_Range = TypeVar("_Range", bound=tuple[int, ...])

__all__ = ["cell_len", "char_width", "UNICODE_VERSION"]

# Parallel arrays for bisect: _W_LOS[i] is the low bound of _W_RANGES[i]
_W_RANGES = WIDTH_RANGES
_W_LOS = [r[0] for r in _W_RANGES]
_A_RANGES = AMBIGUOUS_RANGES
_A_LOS = [r[0] for r in _A_RANGES]

# Codepoints that trigger Tier 3
_ZWJ = 0x200D
_VS15 = 0xFE0E  # text-presentation selector
_VS16 = 0xFE0F  # emoji-presentation selector
_RI_LO, _RI_HI = 0x1F1E6, 0x1F1FF  # regional indicators
_MOD_LO, _MOD_HI = 0x1F3FB, 0x1F3FF  # emoji skin-tone modifiers


def _in_ranges(
    cp: int, ranges: Sequence[_Range], los: Sequence[int]
) -> Optional[_Range]:
    """Return the range containing `cp`, or None if not found.

    Args:
        cp: The codepoint to search for.
        ranges: The range list to search in.
        los: The low bound list for bisecting.

    Returns:
        The range containing `cp`, or None if not found.
    """
    i = bisect_right(los, cp) - 1
    if i >= 0:
        _, hi = ranges[i][0], ranges[i][1]
        if cp <= hi:
            return ranges[i]

    return None


@lru_cache(maxsize=4096)
def char_width(cp: int, east_asian_width: bool = False) -> int:
    """Columns occupied by a single codepoint: 0, 1, or 2.

    `cp` is an int (ordinal). Control characters are out of contract and
    reported as 0. East Asian Ambiguous resolves to 2 only when
    `east_asian_width` is set, else 1.

    Args:
        cp: The codepoint to get the width of.
        east_asian_width: Whether to use East Asian width rules.

    Returns:
        The width of the codepoint, 0, 1, or 2.
    """
    if 0x20 <= cp < 0x7F:  # printable ASCII fast path
        return 1

    if cp < 0x20 or cp == 0x7F:  # control (out of contract)
        return 0

    hit = _in_ranges(cp, _W_RANGES, _W_LOS)
    if hit is not None:
        return hit[2]

    if east_asian_width and _in_ranges(cp, _A_RANGES, _A_LOS) is not None:
        return 2

    return 1


def _has_emoji_complexity(text: str) -> bool:
    """Cheap pre-scan: True if the string needs Tier 3 segmentation.

    Combining marks don't count, Tier 2 already sums them at width 0. Only
    composing/joining codepoints that would otherwise be mis-summed qualify.

    Args:
        text: The string to check.

    Returns:
        True if the string needs Tier 3 segmentation, False otherwise.
    """
    for ch in text:
        cp = ord(ch)
        if cp == _ZWJ or cp == _VS16 or cp == _VS15:
            return True

        if _RI_LO <= cp <= _RI_HI or _MOD_LO <= cp <= _MOD_HI:
            return True

    return False


def _cell_len_simple(text: str, eaw: bool = False) -> int:
    """Tier 2: sum of per-codepoint widths.

    Args:
        text: The string to check.
        eaw: East Asian Width property.

    Returns:
        The sum of per-codepoint widths.
    """
    return sum(char_width(ord(ch), eaw) for ch in text)


def _cell_len_clusters(text: str, eaw: bool = False) -> int:
    """Tier 3: width-aware cluster walk for composed emoji sequences.

    Args:
        text: The string to check.
        eaw: East Asian Width property.

    Returns:
        The sum of per-codepoint widths.
    """
    total = 0
    i = 0
    n = len(text)
    while i < n:
        cp = ord(text[i])

        # Regional indicators pair into a single flag glyph
        if _RI_LO <= cp <= _RI_HI:
            if i + 1 < n and _RI_LO <= ord(text[i + 1]) <= _RI_HI:
                total += 2
                i += 2

            else:
                total += 2  # lone RI: terminal-dependent, treated as wide
                i += 1

            continue

        # Base codepoint, then absorb trailing joiners/selectors/modifiers
        w = char_width(cp, eaw)
        i += 1
        while i < n:
            ncp = ord(text[i])
            if ncp == _ZWJ:
                if i + 1 < n:  # ZWJ + glyph -> one cluster, width 2
                    w = 2
                    i += 2
                    continue

                i += 1  # trailing ZWJ, ignore
                break

            if ncp == _VS16:  # force emoji presentation
                w = 2
                i += 1
                continue

            if ncp == _VS15:  # force text presentation
                w = 1
                i += 1
                continue

            if _MOD_LO <= ncp <= _MOD_HI:  # skin-tone modifier
                w = 2
                i += 1
                continue

            if char_width(ncp, eaw) == 0:  # combining mark
                i += 1
                continue

            break

        total += w

    return total


@lru_cache(maxsize=8192)
def cell_len(text: str, east_asian_width: bool = False) -> int:
    """Number of terminal columns `text` occupies.

    Bounded LRU cache: high-cardinality cell text would otherwise grow the
    cache without limit under long-running `Live` sessions.

    Args:
        text: The text to measure.
        east_asian_width: Whether to use east Asian width rules.

    Returns:
        int: The number of terminal columns the text occupies.
    """
    if text.isascii():  # Tier 1
        return len(text)

    if not _has_emoji_complexity(text):  # Tier 2
        return _cell_len_simple(text, east_asian_width)

    return _cell_len_clusters(text, east_asian_width)  # Tier 3
