//! Width engine accelerator.
//!
//! Mirrors the pure-Python contract in `_width_py.py`:
//!   - `char_width(cp, east_asian_width=False) -> int` (0/1/2)
//!   - `cell_len(text, east_asian_width=False) -> int` (terminal columns)
//!
//! Scalar widths come from `width_table.rs`, generated from the UCD alongside
//! the Python `_width_table.py` so the two engines measure from identical data
//! and policy. Per-cluster width follows the same documented modern-terminal
//! interpretation: ZWJ sequences, flags (regional-indicator pairs), VS16 upgrades,
//! and skin-tone modifiers render as width 2.

mod width_table;

use pyo3::prelude::*;
use unicode_segmentation::UnicodeSegmentation;
use width_table::{AMBIGUOUS_RANGES, UNICODE_VERSION, WIDTH_RANGES};

/// Width of `cp` from WIDTH_RANGES (codepoints whose width is not 1), or None.
#[inline]
fn width_from_table(cp: u32) -> Option<u8> {
    let i = WIDTH_RANGES.partition_point(|&(lo, _, _)| lo <= cp);
    if i == 0 {
        return None;
    }
    let (_, hi, w) = WIDTH_RANGES[i - 1];
    if cp <= hi {
        Some(w)
    } else {
        None
    }
}

/// Whether `cp` is East Asian Ambiguous (resolves to width 2 under CJK policy).
#[inline]
fn is_ambiguous(cp: u32) -> bool {
    let i = AMBIGUOUS_RANGES.partition_point(|&(lo, _)| lo <= cp);
    if i == 0 {
        return false;
    }
    let (_, hi) = AMBIGUOUS_RANGES[i - 1];
    cp <= hi
}

/// Columns occupied by a single scalar; mirrors Python `char_width` exactly.
#[inline]
fn scalar_width(cp: u32, eaw: bool) -> usize {
    if (0x20..0x7F).contains(&cp) {
        return 1; // printable ASCII fast path
    }
    if cp < 0x20 || cp == 0x7F {
        return 0; // control (out of contract)
    }
    if let Some(w) = width_from_table(cp) {
        return w as usize;
    }
    if eaw && is_ambiguous(cp) {
        return 2;
    }
    1
}

fn grapheme_width(g: &str, eaw: bool) -> usize {
    let mut first_is_ri = false;
    let mut special = false;
    for (i, c) in g.chars().enumerate() {
        if i == 0 {
            first_is_ri = ('\u{1F1E6}'..='\u{1F1FF}').contains(&c);
        }
        if c == '\u{200D}'                                   // ZWJ
            || c == '\u{FE0F}'                               // VS16
            || ('\u{1F3FB}'..='\u{1F3FF}').contains(&c)
        // skin-tone modifier
        {
            special = true;
        }
    }
    if special || first_is_ri {
        return 2;
    }
    g.chars().map(|c| scalar_width(c as u32, eaw)).sum()
}

#[pyfunction]
#[pyo3(signature = (cp, east_asian_width = false))]
fn char_width(cp: u32, east_asian_width: bool) -> usize {
    scalar_width(cp, east_asian_width)
}

#[pyfunction]
#[pyo3(signature = (text, east_asian_width = false))]
fn cell_len(text: &str, east_asian_width: bool) -> usize {
    // Tier 1: ASCII fast path (byte length == column count).
    if text.is_ascii() {
        return text.len();
    }
    text.graphemes(true)
        .map(|g| grapheme_width(g, east_asian_width))
        .sum()
}

#[pymodule]
fn _width_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("UNICODE_VERSION", UNICODE_VERSION)?;
    m.add_function(wrap_pyfunction!(char_width, m)?)?;
    m.add_function(wrap_pyfunction!(cell_len, m)?)?;
    Ok(())
}
