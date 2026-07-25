"""Public width-measurement boundary."""

try:
    from ._width_rs import UNICODE_VERSION, cell_len, char_width  # ty: ignore

    _IMPL = "rust"

except ImportError:  # pragma: no cover - exercised by build matrix
    from ._width_py import UNICODE_VERSION, cell_len, char_width

    _IMPL = "python"


def char_cell_len(ch: str) -> int:
    """cell_len for a single character, via the fast int-keyed path.

    Equal to ``cell_len(ch)`` for every character: ASCII counts as 1 (matching
    cell_len's Tier-1 ``len()``), the rare cluster-forming codepoints defer to
    ``cell_len`` (their lone width differs from ``char_width``), and everything
    else uses the int-keyed ``char_width`` lookup — skipping the string-keyed
    LRU and the ``isascii``/emoji-complexity scan that ``cell_len`` runs.

    Args:
        ch: A single character to measure.

    Returns:
        The number of terminal columns the character occupies (0, 1, or 2).
    """
    cp = ord(ch)
    if cp < 0x80:  # ASCII: cell_len uses Tier-1 len() -> 1 per char
        return 1

    if (
        cp == 0x200D  # ZWJ
        or cp == 0xFE0E  # VS15
        or cp == 0xFE0F  # VS16
        or 0x1F1E6 <= cp <= 0x1F1FF  # regional indicators
        or 0x1F3FB <= cp <= 0x1F3FF  # skin-tone modifiers
    ):
        return cell_len(ch)

    return char_width(cp)


__all__ = ["UNICODE_VERSION", "cell_len", "char_cell_len", "char_width"]
