"""Emoji: replace `:shortcode:` tokens with their Unicode glyphs.

`replace` swaps any `:name:` whose name is a known shortcode for the matching
emoji, leaving unknown tokens and stray colons untouched. The shortcode table is
a generated asset (see scripts/gen_emoji_table.py); this module is a pure leaf —
it imports nothing from the public render stack, so it can sit at the bottom of
the dependency graph alongside the width engine.
"""

from __future__ import annotations

import re

from ._emoji_table import EMOJI

# A shortcode is a run of lowercase letters, digits, underscore, plus or hyphen,
# delimited by single colons. Unknown names are left verbatim by the callback.
_CODE_RE = re.compile(r":([a-z0-9_+\-]+):")


def replace(text: str) -> str:
    """Replace known `:shortcode:` tokens in `text` with their emoji glyphs.

    Args:
        text: The text to scan for shortcodes.

    Returns:
        The text with recognised shortcodes substituted, unknown left unchanged.
    """
    if ":" not in text:
        return text

    return _CODE_RE.sub(lambda m: EMOJI.get(m.group(1), m.group(0)), text)
