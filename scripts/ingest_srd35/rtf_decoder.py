from __future__ import annotations

import re

from .constants import IGNORABLE_DESTINATIONS


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


def _append_if_visible(output: list[str], text: str, skip_group: bool) -> None:
    if not skip_group:
        output.append(text)


def decode_rtf_text(rtf_text: str) -> str:
    output: list[str] = []
    i = 0
    uc_skip = 1
    pending_skip = 0
    skip_group = False
    group_just_opened = False
    stack: list[tuple[int, int, bool, bool]] = []
    length = len(rtf_text)

    while i < length:
        char = rtf_text[i]

        if char == "{":
            stack.append((uc_skip, pending_skip, skip_group, group_just_opened))
            group_just_opened = True
            i += 1
            continue

        if char == "}":
            if stack:
                uc_skip, pending_skip, skip_group, group_just_opened = stack.pop()
            i += 1
            continue

        if pending_skip > 0:
            i = _consume_unicode_fallback(rtf_text, i)
            pending_skip -= 1
            continue

        if char != "\\":
            # Ignore physical source line wraps in raw RTF text; semantic newlines
            # are emitted from control words such as \par and \line.
            if char not in "\r\n":
                _append_if_visible(output, char, skip_group)
            if not char.isspace():
                group_just_opened = False
            i += 1
            continue

        i += 1
        if i >= length:
            break

        control_start = rtf_text[i]
        if control_start in "{}\\":
            _append_if_visible(output, control_start, skip_group)
            group_just_opened = False
            i += 1
            continue

        if control_start == "'" and i + 2 < length:
            hex_value = rtf_text[i + 1 : i + 3]
            try:
                _append_if_visible(output, bytes.fromhex(hex_value).decode("cp1252"), skip_group)
            except ValueError:
                pass
            i += 3
            group_just_opened = False
            continue

        if not control_start.isalpha():
            if control_start == "*" and group_just_opened:
                skip_group = True
            if control_start == "~":
                _append_if_visible(output, " ", skip_group)
            elif control_start in {"-", "_"}:
                _append_if_visible(output, "-", skip_group)
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
                _append_if_visible(output, chr(codepoint), skip_group)
            except ValueError:
                pass
            pending_skip = uc_skip
            continue

        if word in {"par", "line", "row"}:
            _append_if_visible(output, "\n", skip_group)
        elif word == "tab":
            _append_if_visible(output, "\t", skip_group)
        elif word == "cell":
            _append_if_visible(output, " | ", skip_group)
        elif word == "emdash":
            _append_if_visible(output, "--", skip_group)
        elif word == "endash":
            _append_if_visible(output, "-", skip_group)
        elif word in {"lquote", "rquote"}:
            _append_if_visible(output, "'", skip_group)
        elif word in {"ldblquote", "rdblquote"}:
            _append_if_visible(output, '"', skip_group)

    text = "".join(output).replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()
