"""Shared fixtures and sample data for the test suite."""

from __future__ import annotations

import io
from typing import Any, Callable, Sequence

import pytest

from fastrich.box import ASCII
from fastrich.console import Console
from fastrich.style import Style
from fastrich.table import Table

# The 6-line no-color rendering of the Name/Age + Alice/Bob table, pinned as a
# golden string shared by test_byte_cache and test_table
ASCII_NAME_AGE_TABLE = (
    "+-------+-----+\n"
    "| Name  | Age |\n"
    "+-------+-----+\n"
    "| Alice | 30  |\n"
    "| Bob   | 100 |\n"
    "+-------+-----+\n"
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear ambient env that could perturb color/width detection in any test."""
    for var in ("NO_COLOR", "FORCE_COLOR", "COLORTERM", "TERM", "COLUMNS"):
        monkeypatch.delenv(var, raising=False)


# Sentinel: derive force_terminal from the color system rather than pinning it
# Passing force_terminal=None explicitly leaves detection to the environment
_DERIVE = object()


class CaptureStdout(io.TextIOWrapper):
    """A text stream over an in-memory byte buffer, modelling real `sys.stdout`.

    Output is captured as raw bytes; read it back with `getvalue()` (bytes)
    or the `text` property (decoded str).
    """

    def __init__(self, **kwargs: Any) -> None:
        """Wrap a fresh BytesIO as a utf-8 text stream.

        Args:
            kwargs: Extra TextIOWrapper options.
        """
        buffer = io.BytesIO()
        super().__init__(buffer, encoding="utf-8", **kwargs)
        self._bytes = buffer

    def getvalue(self) -> bytes:
        """Return the raw bytes written to the underlying binary buffer.

        Returns:
            The captured output bytes.
        """
        return self._bytes.getvalue()

    @property
    def text(self) -> str:
        """Return the captured output decoded to str.

        Returns:
            The captured output as text.
        """
        return self.getvalue().decode()


def _build_console(
    *,
    width: int = 80,
    color: str | None = None,
    force_terminal: Any = _DERIVE,
    **console_kw: Any,
) -> Console:
    """Construct a Console writing to an in-memory buffer.

    The sink models real `sys.stdout` (a text stream over a byte buffer), so
    the console exercises the production byte-output path. `force_terminal`
    defaults to `color is not None` so a color system implies a terminal sink;
    pass `True`/`False` to model a colorless terminal or a piped color console,
    or `None` to leave terminal detection to the environment.

    Args:
        width: The console width.
        color: The color system to use.
        force_terminal: Whether to force a terminal sink, or `None` to detect from environment.
        console_kw: Additional console options.

    Returns:
        The constructed Console.
    """
    if force_terminal is _DERIVE:
        force_terminal = color is not None

    return Console(
        file=CaptureStdout(),
        width=width,
        color_system=color,
        force_terminal=force_terminal,
        **console_kw,
    )


@pytest.fixture
def make_console() -> Callable[..., Console]:
    """Factory for a Console backed by an in-memory buffer.

    `make_console(*, width=80, color=None, force_terminal=None, **console_kw)`.
    Read output back via `console.file.getvalue()` (bytes) or
    `console.file.text` (decoded str), and options via `console.options`.

    Returns:
        The constructed Console.
    """
    return _build_console


@pytest.fixture
def render() -> Callable[..., str]:
    """Factory that renders a renderable and returns the produced string.

    `render(renderable, *, width=80, color=None, force_terminal=None, style=None,
    **console_kw)`. `console_kw` carries Console options such as `markup=`,
    `emoji=` and `theme=`.

    Returns:
        The rendered string.
    """

    def _render(renderable: Any, *, style: str | None = None, **kw: Any) -> str:
        """Render the given renderable to a string using a temporary Console.

        Args:
            renderable: The renderable to render.
            style: The style to apply to the renderable.
            **kw: Console options such as `width`, `color` and `force_terminal`.

        Returns:
            The rendered string.
        """
        console = _build_console(**kw)
        console.print(renderable, style=style)

        return console.file.text

    return _render


@pytest.fixture
def sample_table() -> Callable[[], Table]:
    """Factory for the Name/Age ASCII table with Alice/Bob rows and a red border.

    Returns:
        The constructed Table.
    """

    def _make() -> Table:
        """Construct the Name/Age ASCII table with Alice/Bob rows and a red border.

        Returns:
            The constructed Table.
        """
        t = Table("Name", "Age", box=ASCII, border_style=Style(color="red"))
        t.add_row("Alice", "30")
        t.add_row("Bob", "100")

        return t

    return _make


@pytest.fixture
def simple_table() -> Callable[..., Table]:
    """Factory building a fresh ASCII table from a sequence of row tuples.

    `simple_table(rows, headers=("A", "B"), **table_kw)`, where `table_kw`
    carries Table options such as `show_edge=`, `show_lines=` and `row_styles=`.

    Returns:
        The constructed Table.
    """

    def _make(
        rows: Sequence[tuple[str, ...]],
        headers: Sequence[str] = ("A", "B"),
        **table_kw: Any,
    ) -> Table:
        """Construct an ASCII table from the given rows and headers.

        Args:
            rows: The rows of the table as a sequence of tuples.
            headers: The column headers as a sequence of strings.
            table_kw: Additional Table options.

        Returns:
            The constructed Table.
        """
        t = Table(*headers, box=ASCII, **table_kw)
        for row in rows:
            t.add_row(*row)

        return t

    return _make
