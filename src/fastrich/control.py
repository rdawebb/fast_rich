"""Terminal control sequences: cursor movement, erasing, and screen control.

Builders for ANSI/VT100 control codes, imported by the console for `screen()`,
cursor visibility, and the Live refresh loop. Control codes are pure ASCII, so
sequences are returned as `bytes` (encoded once at module load); the console
writes them directly and suppresses them entirely when the sink is not a
terminal. The small, bounded integer cursor moves are `lru_cache`d, since the
Live loop repositions by a fixed distance every frame. Coordinates in
`move_to`/`move_to_column` are 0-based and converted to the terminal's 1-based
scheme internally.
"""

from __future__ import annotations

from functools import lru_cache

ESC = b"\x1b"
CSI = ESC + b"["

# Cursor visibility
HIDE_CURSOR = CSI + b"?25l"
SHOW_CURSOR = CSI + b"?25h"

# Alternate screen buffer (enter saves the primary screen, exit restores it)
ALT_SCREEN_ENTER = CSI + b"?1049h"
ALT_SCREEN_EXIT = CSI + b"?1049l"

# Absolute positioning / line control
HOME = CSI + b"H"  # Cursor to top-left (row 1, col 1)
CR = b"\r"  # Carriage return: column 1, same row

# Erase
ERASE_LINE = CSI + b"2K"  # Whole current line
ERASE_TO_LINE_END = CSI + b"K"  # From cursor to end of line
ERASE_DOWN = CSI + b"J"  # From cursor to end of screen
CLEAR = CSI + b"2J" + HOME  # Whole screen, then home


@lru_cache(maxsize=64)
def up(count: int = 1) -> bytes:
    """Return the sequence to move the cursor up `count` rows (0 -> no-op).

    Args:
        count: The number of rows to move up.

    Returns:
        The ANSI escape sequence.
    """
    return b"%b%dA" % (CSI, count) if count else b""


@lru_cache(maxsize=64)
def down(count: int = 1) -> bytes:
    """Return the sequence to move the cursor down `count` rows (0 -> no-op).

    Args:
        count: The number of rows to move down.

    Returns:
        The ANSI escape sequence.
    """
    return b"%b%dB" % (CSI, count) if count else b""


@lru_cache(maxsize=64)
def forward(count: int = 1) -> bytes:
    """Return the sequence to move the cursor forward `count` columns (0 -> no-op).

    Args:
        count: The number of columns to move forward.

    Returns:
        The ANSI escape sequence.
    """
    return b"%b%dC" % (CSI, count) if count else b""


@lru_cache(maxsize=64)
def back(count: int = 1) -> bytes:
    """Return the sequence to move the cursor back `count` columns (0 -> no-op).

    Args:
        count: The number of columns to move back.

    Returns:
        The ANSI escape sequence.
    """
    return b"%b%dD" % (CSI, count) if count else b""


def move_to_column(column: int = 0) -> bytes:
    """Return the sequence to move the cursor to a 0-based column on the current row.

    Args:
        column: The column to move to (0-based).

    Returns:
        The ANSI escape sequence.
    """
    return b"%b%dG" % (CSI, column + 1)


def move_to(x: int = 0, y: int = 0) -> bytes:
    """Return the sequence to move the cursor to 0-based (x, y) = (column, row).

    Args:
        x: The column to move to (0-based).
        y: The row to move to (0-based).

    Returns:
        The ANSI escape sequence.
    """
    return b"%b%d;%dH" % (CSI, y + 1, x + 1)
