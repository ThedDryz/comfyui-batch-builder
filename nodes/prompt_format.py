"""Punctuation and spacing for prompt blocks.

Tag blocks become `tag, tag, ` and natural language becomes `Sentence. Sentence. `,
so blocks can be concatenated directly. `{...}` wildcard groups are never split.
"""

import re

_SPACES = re.compile(r"\s+")
_SENTENCE_END = ".!?"


def _split_tags(text):
    """Splits on commas and line breaks outside `{...}` groups; backslash escapes stay whole."""
    tags, buf, depth, i = [], [], 0, 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            buf.append(text[i:i + 2])
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}" and depth:
            depth -= 1
        elif depth == 0 and c in ",\r\n":
            tags.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    tags.append("".join(buf))
    return tags


def format_tags(text):
    tags = []
    for tag in _split_tags(text or ""):
        tag = _SPACES.sub(" ", tag).strip()
        # Only commas inside wildcard groups are left at this point.
        tag = re.sub(r"\s*,\s*", ", ", tag)
        if tag:
            tags.append(tag)
    return "".join(f"{tag}, " for tag in tags)


def format_sentences(text):
    text = _SPACES.sub(" ", text or "").strip()
    text = re.sub(r"\s+([,.!?])", r"\1", text)
    # Digits, closing brackets and `|` after a mark are decimals, weights or wildcard options.
    text = re.sub(r"([.!?])(?=[^\s\d.!?,)\]}|\"'])", r"\1 ", text)
    text = text.rstrip(",").rstrip()
    if not text:
        return ""
    if text[-1] not in _SENTENCE_END:
        text += "."
    return text + " "


def clean_prompt(text):
    """Repairs what wildcard choices can leave behind: empty options, doubled spaces and marks."""
    text = _SPACES.sub(" ", text)
    text = re.sub(r" +,", ",", text)
    text = re.sub(r",(?: ?,)+", ",", text)
    text = re.sub(r"(?<!\.)([.!?])\.(?!\.)", r"\1", text)
    # A sentence end followed by an emptied tag; `\w` keeps tags like `!?` intact.
    text = re.sub(r"(?<=\w)([.!?]) ?,", r"\1", text)
    return text.lstrip(", ").strip()
