"""fastrich — a fast, lean terminal-rendering library.

Submodules load lazily so that importing the package stays cheap.
"""

import importlib

__all__ = ["cell_len", "char_width"]

_LAZY = {
    "cell_len": "fastrich._width",
    "char_width": "fastrich._width",
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
