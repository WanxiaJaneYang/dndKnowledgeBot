"""Shared types for span-level RTF decoding output.

A TextSpan represents a contiguous run of visible text with uniform
formatting. The RTF decoder emits a list of TextSpans; the IR builder
collapses them into blocks with summary formatting fields.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextSpan:
    """A contiguous run of visible text with uniform formatting.

    text: the visible text. \\par / \\line emit "\\n" within text; the
        decoder does not split spans on these newlines.
    font_size: half-points (RTF native unit). 24 == 12pt body. 0 if
        the document declares no default and no \\fs override is in
        scope.
    bold: True if \\b1 (or \\b alone) is in scope, False if \\b0 or
        no \\b override is in scope.
    """
    text: str
    font_size: int
    bold: bool
