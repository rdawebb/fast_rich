"""Theme: named styles resolved during markup parsing.

A Theme maps semantic names (e.g. "danger") to Styles. String style values are
parsed once, at construction. `inherit` controls whether a theme starts from the
built-in defaults (currently minimal). With no theme set, names fall through to
`Style.parse`, so existing behaviour is unchanged.
"""

from __future__ import annotations

from typing import Mapping

from .style import Style

# Built-in semantic styles, intentionally minimal for now
DEFAULT_STYLES: dict[str, Style] = {}


def _as_style(value: Style | str) -> Style:
    """Coerce a style value to a Style, parsing definition strings.

    Args:
        value: A Style or a style definition string.

    Returns:
        The Style.
    """
    return value if isinstance(value, Style) else Style.parse(value)


class Theme:
    """A mapping of semantic style names to Styles."""

    def __init__(
        self,
        styles: Mapping[str, Style | str] | None = None,
        *,
        inherit: bool = True,
    ) -> None:
        """Initialise a Theme.

        Args:
            styles: Mapping of name -> Style (or a style definition string).
            inherit: Start from the built-in default styles before applying
                `styles`. Defaults to True.
        """
        self.styles: dict[str, Style] = dict(DEFAULT_STYLES) if inherit else {}
        if styles:
            for name, value in styles.items():
                self.styles[name] = _as_style(value)

    def get(self, name: str) -> Style | None:
        """Return the Style registered for `name`, or None if absent.

        Args:
            name: The style name to look up.

        Returns:
            The Style, or None when the name is not in the theme.
        """
        return self.styles.get(name)
