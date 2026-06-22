"""Public width-measurement boundary."""

try:
    from ._width_rs import UNICODE_VERSION, cell_len, char_width  # ty: ignore

    _IMPL = "rust"

except ImportError:  # pragma: no cover - exercised by build matrix
    from ._width_py import UNICODE_VERSION, cell_len, char_width

    _IMPL = "python"

__all__ = ["cell_len", "char_width", "UNICODE_VERSION"]
