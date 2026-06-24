"""fastrich — a fast, lean terminal-rendering library.

Submodules load lazily so that importing the package stays cheap.
"""

import importlib

__all__ = [
    "cell_len",
    "char_width",
    "Style",
    "Text",
    "Segment",
    "Console",
    "ConsoleOptions",
    "Table",
    "box",
    "Panel",
    "Rule",
    "Padding",
    "Align",
    "Columns",
    "Measurement",
    "markup",
]

_LAZY = {
    "cell_len": "fastrich._width",
    "char_width": "fastrich._width",
    "Style": "fastrich.style",
    "Text": "fastrich.text",
    "Segment": "fastrich.segment",
    "Console": "fastrich.console",
    "ConsoleOptions": "fastrich.console",
    "Table": "fastrich.table",
    "box": "fastrich.box",
    "Panel": "fastrich.panel",
    "Rule": "fastrich.rule",
    "Padding": "fastrich.padding",
    "Align": "fastrich.align",
    "Columns": "fastrich.columns",
    "Measurement": "fastrich.measure",
    "markup": "fastrich.markup",
}


def __getattr__(name) -> object:
    """Lazily load submodules.

    Args:
        name: The name of the attribute to load.

    Returns:
        object: The loaded attribute.
    """
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module 'fastrich' has no attribute {name!r}")

    module = importlib.import_module(target)

    return getattr(module, name)
