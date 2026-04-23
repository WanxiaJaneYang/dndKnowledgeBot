from __future__ import annotations

import re
from typing import Iterator

from .constants import IGNORABLE_DESTINATIONS
from .text_spans import TextSpan


_DEFAULT_FONT_SIZE = 24  # half-points; 12pt is the typical body default


def _consume_unicode_fallback(rtf_text: str, start_index: int) -> int:
    i = start_index
    length = len(rtf_text)
    if i >= length:
        return i

    if rtf_text[i] != "\\":
        return i + 1

    if i + 1 >= length:
        return i + 1

    nxt = rtf_text[i + 1]
    if nxt == "'" and i + 3 < length:
        return i + 4
    if nxt in "{}\\":
        return i + 2
    return i + 1


def _parse_rtf(rtf_text: str) -> Iterator[tuple[str, int, bool]]:
    """Internal generator yielding (visible_text_chunk, font_size, bold).

    Each yielded tuple is one chunk of visible text along with the
    formatting state in scope at the time the text was emitted.
    Adjacent chunks may share formatting; collapsing them is the
    caller's responsibility.
    """
    i = 0
    uc_skip = 1
    pending_skip = 0
    skip_group = False
    group_just_opened = False
    current_fs = _DEFAULT_FONT_SIZE
    current_bold = False
    # Stack frames: (uc_skip, pending_skip, skip_group, group_just_opened, current_fs, current_bold)
    stack: list[tuple[int, int, bool, bool, int, bool]] = []
    length = len(rtf_text)

    def emit(text: str) -> Iterator[tuple[str, int, bool]]:
        if text and not skip_group:
            yield (text, current_fs, current_bold)

    while i < length:
        char = rtf_text[i]

        if char == "{":
            stack.append((uc_skip, pending_skip, skip_group, group_just_opened, current_fs, current_bold))
            group_just_opened = True
            i += 1
            continue

        if char == "}":
            if stack:
                uc_skip, pending_skip, skip_group, group_just_opened, current_fs, current_bold = stack.pop()
            i += 1
            continue

        if pending_skip > 0:
            i = _consume_unicode_fallback(rtf_text, i)
            pending_skip -= 1
            continue

        if char != "\\":
            if char not in "\r\n":
                yield from emit(char)
            if not char.isspace():
                group_just_opened = False
            i += 1
            continue

        i += 1
        if i >= length:
            break

        control_start = rtf_text[i]
        if control_start in "{}\\":
            yield from emit(control_start)
            group_just_opened = False
            i += 1
            continue

        if control_start == "'" and i + 2 < length:
            hex_value = rtf_text[i + 1 : i + 3]
            try:
                yield from emit(bytes.fromhex(hex_value).decode("cp1252"))
            except ValueError:
                pass
            i += 3
            group_just_opened = False
            continue

        if not control_start.isalpha():
            if control_start == "*" and group_just_opened:
                skip_group = True
            if control_start == "~":
                yield from emit(" ")
            elif control_start in {"-", "_"}:
                yield from emit("-")
            if not control_start.isspace():
                group_just_opened = False
            i += 1
            continue

        start = i
        while i < length and rtf_text[i].isalpha():
            i += 1
        word = rtf_text[start:i]

        sign = 1
        if i < length and rtf_text[i] in {"+", "-"}:
            if rtf_text[i] == "-":
                sign = -1
            i += 1

        num_start = i
        while i < length and rtf_text[i].isdigit():
            i += 1
        numeric = int(rtf_text[num_start:i]) * sign if i > num_start else None

        if i < length and rtf_text[i] == " ":
            i += 1

        if group_just_opened and word in IGNORABLE_DESTINATIONS:
            skip_group = True
        group_just_opened = False

        if word == "uc" and numeric is not None:
            uc_skip = max(numeric, 0)
            continue
        if word == "u" and numeric is not None:
            codepoint = numeric if numeric >= 0 else numeric + 65536
            try:
                yield from emit(chr(codepoint))
            except ValueError:
                pass
            pending_skip = uc_skip
            continue

        if word == "fs" and numeric is not None:
            current_fs = numeric
            continue
        if word == "b":
            # \b1 turns on; \b0 turns off; bare \b is ON.
            current_bold = numeric is None or numeric != 0
            continue

        if word in {"par", "line", "row"}:
            yield from emit("\n")
        elif word == "tab":
            yield from emit("\t")
        elif word == "cell":
            yield from emit(" | ")
        elif word == "emdash":
            yield from emit("--")
        elif word == "endash":
            yield from emit("-")
        elif word in {"lquote", "rquote"}:
            yield from emit("'")
        elif word in {"ldblquote", "rdblquote"}:
            yield from emit('"')


def _normalize_text(text: str) -> str:
    text = text.replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def decode_rtf_text(rtf_text: str) -> str:
    """Decode RTF to plain text. Backwards-compatible API."""
    parts: list[str] = []
    for chunk, _fs, _b in _parse_rtf(rtf_text):
        parts.append(chunk)
    return _normalize_text("".join(parts))


def decode_rtf_spans(rtf_text: str) -> list[TextSpan]:
    """Decode RTF to a list of TextSpan with formatting metadata.

    Adjacent chunks with identical (font_size, bold) state are merged
    into a single TextSpan. Whitespace normalization is NOT applied at
    this layer (spans preserve raw newlines from \\par); callers that
    want collapsed text should join span.text values and pass them
    through their own normalization.
    """
    spans: list[TextSpan] = []
    for chunk, fs, bold in _parse_rtf(rtf_text):
        if spans and spans[-1].font_size == fs and spans[-1].bold == bold:
            last = spans[-1]
            spans[-1] = TextSpan(text=last.text + chunk, font_size=fs, bold=bold)
        else:
            spans.append(TextSpan(text=chunk, font_size=fs, bold=bold))
    return spans
