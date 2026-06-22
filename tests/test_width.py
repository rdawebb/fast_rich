"""Golden width fixtures spanning all three tiers."""

import pytest

from fastrich._width import UNICODE_VERSION, cell_len, char_width


def test_pinned_version() -> None:
    """Test pinned Unicode version."""
    assert UNICODE_VERSION == "17.0.0"


@pytest.mark.parametrize(
    "text, expected",
    [
        # Tier 1: ASCII
        ("", 0),
        ("hello world", 11),
        ("ERROR: nope", 11),
        # Tier 2: CJK / wide
        ("日本語", 6),
        ("한국어", 6),
        ("ＡＢＣ", 6),  # fullwidth latin
        ("中文a", 5),
        # Tier 2: combining marks (no Tier 3 needed)
        ("cafe\u0301", 4),  # e + combining acute
        ("a\u0300\u0301", 1),  # base + two combining
        # Tier 3: emoji presentation via VS16
        ("\u2602", 1),  # umbrella, text presentation
        ("\u2602\ufe0f", 2),  # umbrella + VS16 -> emoji width
        ("\u2603\ufe0e", 1),  # snowman + VS15 -> text width
        # Tier 3: standalone wide emoji (also fine in Tier 2)
        ("\U0001f680", 2),  # rocket
        # Tier 3: skin-tone modifier
        ("\U0001f44d\U0001f3fd", 2),  # thumbs up + medium skin tone
        # Tier 3: ZWJ family -> single glyph
        ("\U0001f468\u200d\U0001f469\u200d\U0001f467\u200d\U0001f466", 2),
        # Tier 3: regional indicator pair -> one flag
        ("\U0001f1ec\U0001f1e7", 2),  # GB flag
        # Tier 3: mixed run
        ("ok \U0001f680 go", 8),  # "ok " (3) + rocket (2) + " go" (3)
    ],
)
def test_cell_len(text, expected) -> None:
    """Test cell_len with various input strings."""
    assert cell_len(text) == expected


def test_ambiguous_policy() -> None:
    """Test ambiguous policy handling."""
    # U+2018 LEFT SINGLE QUOTE is East Asian Ambiguous
    assert cell_len("\u2018") == 1
    assert cell_len("\u2018", east_asian_width=True) == 2


def test_char_width_basics() -> None:
    """Test char_width with basic character inputs."""
    assert char_width(ord("A")) == 1
    assert char_width(ord("中")) == 2
    assert char_width(0x0301) == 0  # combining acute
    assert char_width(0x09) == 0  # control, out of contract
