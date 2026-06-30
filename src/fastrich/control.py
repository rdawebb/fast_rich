"""Terminal control sequences: cursor movement, erasing, and screen control.

A pure leaf — string builders for ANSI/VT100 control codes, imported by the
console for `screen()`, cursor visibility, and (later) the Live refresh loop.
Sequences are returned as `str`; the console encodes and writes them, and
suppresses them entirely when the sink is not a terminal.

Coordinates in `move_to`/`move_to_column` are 0-based at this API and converted
to the terminal's 1-based scheme internally.
"""

from __future__ import annotations

ESC = "\x1b"
CSI = ESC + "["

# Cursor visibility
HIDE_CURSOR = CSI + "?25l"
SHOW_CURSOR = CSI + "?25h"

# Alternate screen buffer (enter saves the primary screen, exit restores it)
ALT_SCREEN_ENTER = CSI + "?1049h"
ALT_SCREEN_EXIT = CSI + "?1049l"

# Absolute positioning / line control
HOME = CSI + "H"  # Cursor to top-left (row 1, col 1)
CR = "\r"  # Carriage return: column 1, same row

# Erase
ERASE_LINE = CSI + "2K"  # Whole current line
ERASE_TO_LINE_END = CSI + "K"  # From cursor to end of line
ERASE_DOWN = CSI + "J"  # From cursor to end of screen
CLEAR = CSI + "2J" + HOME  # Whole screen, then home


def up(count: int = 1) -> str:
    """Return the sequence to move the cursor up `count` rows (0 -> no-op).

    Args:
        count: The number of rows to move up.

    Returns:
        The ANSI escape sequence.
    """
    return f"{CSI}{count}A" if count else ""


def down(count: int = 1) -> str:
    """Return the sequence to move the cursor down `count` rows (0 -> no-op).

    Args:
        count: The number of rows to move down.

    Returns:
        The ANSI escape sequence.
    """
    return f"{CSI}{count}B" if count else ""


def forward(count: int = 1) -> str:
    """Return the sequence to move the cursor forward `count` columns (0 -> no-op).

    Args:
        count: The number of columns to move forward.

    Returns:
        The ANSI escape sequence.
    """
    return f"{CSI}{count}C" if count else ""


def back(count: int = 1) -> str:
    """Return the sequence to move the cursor back `count` columns (0 -> no-op).

    Args:
        count: The number of columns to move back.

    Returns:
        The ANSI escape sequence.
    """
    return f"{CSI}{count}D" if count else ""


def move_to_column(column: int = 0) -> str:
    """Return the sequence to move the cursor to a 0-based column on the current row.

    Args:
        column: The column to move to (0-based).

    Returns:
        The ANSI escape sequence.
    """
    return f"{CSI}{column + 1}G"


def move_to(x: int = 0, y: int = 0) -> str:
    """Return the sequence to move the cursor to 0-based (x, y) = (column, row).

    Args:
        x: The column to move to (0-based).
        y: The row to move to (0-based).

    Returns:
        The ANSI escape sequence.
    """
    return f"{CSI}{y + 1};{x + 1}H"
