"""Generate fastrich/_width/_width_table.py from the Unicode Character Database.

Width assignment precedence (first match wins):
    Default_Ignorable / Cf / Cc / Mn / Me        -> 0
    Hangul Jungseong (V) / Jongseong (T) jamo    -> 0
    EastAsianWidth W or F                        -> 2
    everything else                              -> 1

Conjoining Hangul jamo (Hangul_Syllable_Type V and T) are category Lo with
EastAsianWidth N, so they would otherwise resolve to 1. They compose onto a
leading consonant (type L, which is wide), so a decomposed syllable L+V+T must
measure 2, not 4; forced to 0 to match terminal rendering and wcwidth.

East Asian Ambiguous (A) is emitted as a separate table, so the runtime resolves
it to 1 or 2 per the eaw policy.

Usage:
    python scripts/gen_width_table.py [--version 17.0.0] [--out PATH]
"""

import argparse
import sys
import urllib.request
from pathlib import Path

PINNED_VERSION = "17.0.0"
UCD_BASE = "https://www.unicode.org/Public/{version}/ucd/"

# UCD files consumed, default-wide emoji are covered by EastAsianWidth (W/F)
FILES = {
    "eaw": "EastAsianWidth.txt",
    "gc": "extracted/DerivedGeneralCategory.txt",
    "dcp": "DerivedCoreProperties.txt",
    "hst": "HangulSyllableType.txt",
}


def _fetch(version, relpath) -> str:
    """Fetch a UCD file from the given version and relative path.

    Args:
        version: The Unicode version to fetch (e.g. "17.0.0").
        relpath: The relative path of the file to fetch (e.g. "EastAsianWidth.txt").

    Returns:
        The contents of the fetched file as a string.
    """
    url = UCD_BASE.format(version=version) + relpath
    print(f"  fetching {url}", file=sys.stderr)
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode("utf-8")


def _iter_records(text):
    """Yield (lo, hi, value) from a standard UCD '<range> ; <value>' file.

    Args:
        text: The contents of the file to parse.

    Yields:
        Tuples of (lo, hi, value) where lo and hi are the start and end code points,
        and value is the width value.
    """
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue

        field, _, value = line.partition(";")
        value = value.strip()
        field = field.strip()
        if ".." in field:
            lo_s, hi_s = field.split("..")
            lo, hi = int(lo_s, 16), int(hi_s, 16)

        else:
            lo = hi = int(field, 16)

        yield lo, hi, value


def build_tables(version) -> tuple[dict[int, str], set[int]]:
    """Build the EAW and zero width tables for the given Unicode version.

    Args:
        version: The Unicode version to build tables for (e.g. "17.0.0").

    Returns:
        A tuple of (eaw, zero) where eaw is a dictionary mapping code points to EAW values,
        and zero is a set of code points with width 0.
    """
    eaw_txt = _fetch(version, FILES["eaw"])
    gc_txt = _fetch(version, FILES["gc"])
    dcp_txt = _fetch(version, FILES["dcp"])
    hst_txt = _fetch(version, FILES["hst"])

    MAX = 0x110000
    eaw = {}  # cp -> EAW value
    for lo, hi, val in _iter_records(eaw_txt):
        for cp in range(lo, hi + 1):
            eaw[cp] = val

    zero = set()  # cp -> width 0
    for lo, hi, val in _iter_records(gc_txt):
        if val in ("Mn", "Me", "Cf", "Cc"):
            zero.update(range(lo, hi + 1))

    for lo, hi, val in _iter_records(dcp_txt):
        if val == "Default_Ignorable_Code_Point":
            zero.update(range(lo, hi + 1))

    for lo, hi, val in _iter_records(hst_txt):
        if val in ("V", "T"):  # conjoining jungseong/jongseong jamo
            zero.update(range(lo, hi + 1))

    def width_of(cp) -> int:
        """Return the width of the given code point.

        Args:
            cp: The code point to get the width of.

        Returns:
            The width of the code point (0, 1, or 2).
        """
        if cp in zero:
            return 0

        v = eaw.get(cp)
        if v in ("W", "F"):
            return 2

        return 1  # N, Na, H, and A all narrow here; A handled separately

    width_ranges = _coalesce(
        (cp, w) for cp, w in ((cp, width_of(cp)) for cp in range(MAX)) if w != 1
    )
    ambiguous_ranges = _coalesce_flag(cp for cp in range(MAX) if eaw.get(cp) == "A")

    return width_ranges, ambiguous_ranges


def _coalesce(pairs):
    """Collapse (cp, width) into sorted (lo, hi, width) runs.

    Args:
        pairs: An iterable of (cp, width) pairs.

    Returns:
        A list of (lo, hi, width) tuples representing the coalesced runs.
    """
    out = []
    start = prev = None
    cur_w = None
    for cp, w in sorted(pairs):
        if prev is None:
            start = prev = cp
            cur_w = w

        elif cp == prev + 1 and w == cur_w:
            prev = cp

        else:
            out.append((start, prev, cur_w))
            start = prev = cp
            cur_w = w

    if start is not None:
        out.append((start, prev, cur_w))

    return out


def _coalesce_flag(cps):
    """Collapse a set of codepoints into sorted (lo, hi) runs.

    Args:
        cps: An iterable of codepoints.

    Returns:
        A list of (lo, hi) tuples representing the coalesced runs.
    """
    out = []
    start = prev = None
    for cp in sorted(cps):
        if prev is None:
            start = prev = cp

        elif cp == prev + 1:
            prev = cp

        else:
            out.append((start, prev))
            start = prev = cp

    if start is not None:
        out.append((start, prev))

    return out


def render_module(version, width_ranges, ambiguous_ranges) -> str:
    """Render the width table module as a string.

    Args:
        version: The Unicode version string.
        width_ranges: A list of (lo, hi, width) tuples for width ranges.
        ambiguous_ranges: A list of (lo, hi) tuples for ambiguous character ranges.

    Returns:
        The rendered width table module as a string.
    """

    def fmt3(rs) -> str:
        """Format a list of (lo, hi, width) tuples as a string.

        Args:
            rs: A list of (lo, hi, width) tuples.

        Returns:
            The formatted string.
        """
        return "\n".join(f"    (0x{lo:04X}, 0x{hi:04X}, {w})," for lo, hi, w in rs)

    def fmt2(rs) -> str:
        """Format a list of (lo, hi) tuples as a string.

        Args:
            rs: A list of (lo, hi) tuples.

        Returns:
            The formatted string.
        """
        return "\n".join(f"    (0x{lo:04X}, 0x{hi:04X})," for lo, hi in rs)

    return (
        '"""GENERATED FILE — do not edit by hand.\n\n'
        "Produced by scripts/gen_width_table.py. Re-run to regenerate.\n"
        '"""\n\n'
        f'UNICODE_VERSION = "{version}"\n\n'
        "WIDTH_RANGES = (\n" + fmt3(width_ranges) + "\n)\n\n"
        "AMBIGUOUS_RANGES = (\n" + fmt2(ambiguous_ranges) + "\n)\n"
    )


def main() -> None:
    """Generate the width table module for the given Unicode version."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=PINNED_VERSION)
    ap.add_argument(
        "--out",
        default=str(
            Path(__file__).resolve().parent.parent
            / "src"
            / "fastrich"
            / "_width"
            / "_width_table.py"
        ),
    )
    args = ap.parse_args()

    print(f"generating width table for Unicode {args.version}", file=sys.stderr)
    width_ranges, ambiguous_ranges = build_tables(args.version)
    module = render_module(args.version, width_ranges, ambiguous_ranges)
    Path(args.out).write_text(module, encoding="utf-8")
    print(
        f"wrote {args.out}: {len(width_ranges)} width ranges, "
        f"{len(ambiguous_ranges)} ambiguous ranges",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
