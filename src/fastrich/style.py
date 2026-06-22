"""Style an immutable, hashable text style that compiles to a cached SGR string.

A Style records each attribute as a tri-state: `True` (on), `False` (explicitly
off), or `None` (unset → inherit). Combining layers one style over another:
set fields win, unset fields fall through. The SGR escape is built once and cached.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

# Attribute name -> SGR "on" code
_ATTR_CODES = {
    "bold": 1,
    "dim": 2,
    "italic": 3,
    "underline": 4,
    "blink": 5,
    "reverse": 7,
    "conceal": 8,
    "strike": 9,
}
# Standard color name -> offset from the base (30 fg / 40 bg), bright adds 60
_COLORS = {
    "black": 0,
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
    "magenta": 5,
    "cyan": 6,
    "white": 7,
}
_RESET = "\x1b[0m"

_FIELDS = (
    "bold",
    "dim",
    "italic",
    "underline",
    "blink",
    "reverse",
    "conceal",
    "strike",
    "color",
    "bgcolor",
)


def _color_sgr(name: str, base: int) -> str:
    """Return the SGR code for the given color name and base (30 or 40).

    Args:
        name: The color name (e.g. "red", "bright_blue").
        base: The base offset (30 for fg, 40 for bg).

    Returns:
        The SGR code as a string.

    Raises:
        ValueError: If the color name is unknown.
    """
    bright = name.startswith("bright_")
    key = name[7:] if bright else name
    idx = _COLORS.get(key)

    if idx is None:
        raise ValueError(f"unknown color: {name!r}")

    return str(base + idx + (60 if bright else 0))


class Style:
    """Style represents a rich text style, including SGR codes for color and formatting."""

    __slots__ = (*_FIELDS, "_key", "_sgr")

    def __init__(
        self,
        *,
        bold: bool | None = None,
        dim: bool | None = None,
        italic: bool | None = None,
        underline: bool | None = None,
        blink: bool | None = None,
        reverse: bool | None = None,
        conceal: bool | None = None,
        strike: bool | None = None,
        color: str | None = None,
        bgcolor: str | None = None,
    ) -> None:
        """Initialise a Style with the given formatting options.

        Args:
            bold: Whether to apply bold formatting.
            dim: Whether to apply dim formatting.
            italic: Whether to apply italic formatting.
            underline: Whether to apply underline formatting.
            blink: Whether to apply blink formatting.
            reverse: Whether to apply reverse formatting.
            conceal: Whether to apply conceal formatting.
            strike: Whether to apply strike formatting.
            color: The color to apply.
            bgcolor: The background color to apply.
        """
        self.bold = bold
        self.dim = dim
        self.italic = italic
        self.underline = underline
        self.blink = blink
        self.reverse = reverse
        self.conceal = conceal
        self.strike = strike
        self.color = color
        self.bgcolor = bgcolor
        self._key = (
            bold,
            dim,
            italic,
            underline,
            blink,
            reverse,
            conceal,
            strike,
            color,
            bgcolor,
        )
        self._sgr = None

    def __eq__(self, other: object) -> bool:
        """Return whether this style is equal to another style.

        Args:
            other: The other style to compare with.

        Returns:
            True if the styles are equal, False otherwise.
        """
        return isinstance(other, Style) and self._key == other._key

    def __hash__(self) -> int:
        """Return the hash of this style."""
        return hash(self._key)

    def __bool__(self) -> bool:
        """Return whether this style is truthy (has any fields set).

        Returns:
            True if the style has any fields set, False otherwise.
        """
        return any(v is not None for v in self._key)

    def __repr__(self) -> str:
        """Return the string representation of this style.

        Returns:
            The string representation of this style.
        """
        set_fields = ", ".join(
            f"{f}={v!r}" for f, v in zip(_FIELDS, self._key) if v is not None
        )

        return f"Style({set_fields})"

    def combine(self, other: "Style") -> "Style":
        """Layer `other` over `self`: set fields in other win, else inherit.

        Args:
            other: The other style to combine with.

        Returns:
            The combined style.
        """
        if not other:
            return self

        merged: dict[str, Any] = {
            f: (o if o is not None else s)
            for f, s, o in zip(_FIELDS, self._key, other._key)
        }

        return Style(**merged)

    __add__ = combine

    @property
    def sgr(self) -> str:
        """The `\\x1b[...m` prefix for this style (empty if no codes).

        Returns:
            The SGR prefix for this style.
        """
        if self._sgr is None:
            codes = [str(c) for name, c in _ATTR_CODES.items() if getattr(self, name)]

            if self.color:
                codes.append(_color_sgr(self.color, 30))

            if self.bgcolor:
                codes.append(_color_sgr(self.bgcolor, 40))

            self._sgr = f"\x1b[{';'.join(codes)}m" if codes else ""

        return self._sgr

    def render(self, text: str) -> str:
        """Wrap `text` in this style's SGR + reset (plain if no style).

        Args:
            text: The text to render.

        Returns:
            The text wrapped in this style's SGR + reset (plain if no style).
        """
        sgr = self.sgr
        return f"{sgr}{text}{_RESET}" if sgr else text

    @classmethod
    def parse(cls, definition: str) -> "Style":
        """Parse a style definition string into a `Style` instance.

        Args:
            definition: The style definition string.

        Returns:
            The parsed `Style` instance.
        """
        return _parse(definition)


NULL_STYLE = Style()


@lru_cache(maxsize=1024)
def _parse(definition: str) -> "Style":
    """Parse a style definition string into a `Style` instance.

    Args:
        definition: The style definition string.

    Returns:
        The parsed `Style` instance.

    Raises:
        ValueError: If an unknown style token is encountered.
    """
    kw: dict[str, Any] = {}
    tokens = iter(definition.split())
    for tok in tokens:
        if tok == "on":  # background follows
            kw["bgcolor"] = next(tokens)
            continue

        if tok in _ATTR_CODES:
            kw[tok] = True
            continue

        name = tok[7:] if tok.startswith("bright_") else tok
        if name in _COLORS:
            kw["color"] = tok
            continue

        raise ValueError(f"unknown style token: {tok!r}")

    return Style(**kw)
