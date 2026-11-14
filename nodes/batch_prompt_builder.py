import json
import logging
import re
from dataclasses import dataclass, field

from . import wildcard
from .character_definition import (
    DROP_KEYWORDS,
    MULTILINE_INT,
    MULTILINE_TEXT,
    PARTS,
    ROLL_TEXT,
    TEXT,
    join_parts,
)

try:
    from comfy_execution.graph import ExecutionBlocker
except ImportError:
    ExecutionBlocker = None

CATEGORY = "prompt/batch"
MAX_INDEX = 100000
DEFAULT_SIZE = 1024
MIN_SIZE = 64

log = logging.getLogger("BatchPrompt")


def split_lines(text):
    return text.splitlines() if text else []


def pick_size(lines, idx, side, line, warnings):
    """Size for prompt line `line`; the last entry is reused when the list is shorter."""
    if not lines:
        return DEFAULT_SIZE
    raw = (lines[idx] if idx < len(lines) else lines[-1]).strip()
    try:
        size = int(raw)
    except ValueError:
        size = 0
    if size <= 0:
        warnings.append(f"{side} on line {line} is not a positive integer ({raw!r}); using {DEFAULT_SIZE}")
        return DEFAULT_SIZE
    # Latents are 1/8 of the image size, so only multiples of 8 are representable.
    snapped = max(MIN_SIZE, size // 8 * 8)
    if snapped != size:
        warnings.append(f"{side} {size} on line {line} rounded to {snapped} (multiple of 8)")
    return snapped


def empty_latent(width, height):
    import comfy.model_management
    import torch

    device = comfy.model_management.intermediate_device()
    return {"samples": torch.zeros([1, 4, height // 8, width // 8], device=device)}


def parse_keywords(line):
    return [t for t in re.split(r"[\s,]+", line) if t]


def parse_character(character):
    """Returns (parts dict or None, plain text fallback)."""
    if not character or not character.strip():
        return None, ""
    try:
        data = json.loads(character)
        parts = data["parts"]
        if isinstance(parts, dict):
            return parts, ""
    except (ValueError, KeyError, TypeError):
        pass
    return None, character


@dataclass
class BatchResult:
    line: int
    last_line: int
    done: bool = False
    prompts: list = field(default_factory=list)
    seeds: list = field(default_factory=list)
    template: str = ""
    dropped: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    advance: bool = False
    next_index: int = 0
    width: int = DEFAULT_SIZE
    height: int = DEFAULT_SIZE

    @property
    def status(self):
        if self.done:
            text = f"done: line {self.line} is past the last line {self.last_line}"
        else:
            text = f"line {self.line} of {self.last_line} | {len(self.prompts)} variant(s)"
            text += f" | {self.width}x{self.height}"
            text += f" | dropped: {', '.join(self.dropped) if self.dropped else 'none'}"
            text += f" | next: {self.next_index}" if self.advance else " | last line"
        if self.warnings:
            text += "\nwarnings:\n- " + "\n- ".join(self.warnings)
        return text


def build_batch(
    start_index,
    end_index,
    batch,
    prepend="",
    append="",
    booru="",
    natural="",
    character_booleans="",
    character=None,
    seeds=(),
    auto_advance=True,
    width="",
    height="",
):
    booru_lines = split_lines(booru)
    natural_lines = split_lines(natural)
    keyword_lines = split_lines(character_booleans)
    width_lines = split_lines(width)
    height_lines = split_lines(height)
    warnings = []

    if booru_lines and natural_lines and len(booru_lines) != len(natural_lines):
        warnings.append(
            f"booru has {len(booru_lines)} lines but natural has {len(natural_lines)}; "
            "the shorter list is padded with empty lines"
        )
    line_count = max(len(booru_lines), len(natural_lines), 1)
    if keyword_lines and len(keyword_lines) < line_count:
        warnings.append(
            f"character booleans has {len(keyword_lines)} lines for {line_count} prompt lines; "
            "missing lines use the Character Definition switches"
        )
    for side, lines in (("width", width_lines), ("height", height_lines)):
        if lines and len(lines) < line_count:
            warnings.append(
                f"{side} has {len(lines)} lines for {line_count} prompt lines; "
                f"missing lines reuse the last {side}"
            )

    last_line = line_count if end_index <= 0 else min(end_index, line_count)
    line = max(start_index, 1)
    result = BatchResult(line=line, last_line=last_line, warnings=warnings)
    if line > last_line:
        result.done = True
        return result

    idx = line - 1
    booru_line = booru_lines[idx] if idx < len(booru_lines) else ""
    natural_line = natural_lines[idx] if idx < len(natural_lines) else ""
    keywords = parse_keywords(keyword_lines[idx]) if idx < len(keyword_lines) else []
    result.width = pick_size(width_lines, idx, "width", line, warnings)
    result.height = pick_size(height_lines, idx, "height", line, warnings)

    unknown = [k for k in keywords if k not in DROP_KEYWORDS]
    if unknown:
        warnings.append(f"unknown keyword(s) on line {line}: {', '.join(unknown)}")

    parts, plain = parse_character(character)
    if parts is not None:
        kept = []
        for key, label, keyword in PARTS:
            part = parts.get(key) or {}
            text = part.get("text", "")
            if not part.get("enabled", True) or not text.strip():
                continue
            if keyword and keyword in keywords:
                result.dropped.append(label)
                continue
            kept.append(text)
        appearance = join_parts(kept)
    else:
        if plain:
            warnings.append("character input is not from Character Definition; it is used as-is")
        appearance = plain.strip()

    segments = (prepend, booru_line, natural_line, appearance, append)
    result.template = " ".join(s.strip() for s in segments if s and s.strip())

    template = wildcard.parse(result.template)
    warnings.extend(template.errors)

    seeds = list(seeds)
    if not seeds:
        raise ValueError("Batch Prompt Builder needs at least one seed; connect a Seed List.")
    if len(seeds) < batch:
        warnings.append(f"batch is {batch} but only {len(seeds)} seed(s) are connected; using {len(seeds)}")
    result.seeds = seeds[:batch]
    result.prompts = [template.resolve(s).strip() for s in result.seeds]

    if auto_advance and line < last_line:
        result.advance = True
        result.next_index = line + 1
    return result


def _first(value, default=None):
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default


class BatchPromptBuilder:
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING", "INT", "STRING", "STRING", "LATENT")
    RETURN_NAMES = ("prompts", "seeds", "template", "status", "latent")
    OUTPUT_IS_LIST = (True, True, False, False, False)
    INPUT_IS_LIST = True
    OUTPUT_NODE = True
    FUNCTION = "build"
    DESCRIPTION = (
        "Builds the prompt for line `start_index` (prepend, booru, natural, character, append), "
        "resolves {a|b} wildcards once per seed, then advances to the next line and queues again "
        "until `end_index`. Queue with batch count 1."
    )

    @classmethod
    def INPUT_TYPES(cls):
        def text(title, placeholder, tooltip, **extra):
            return (
                ROLL_TEXT,
                {"default": "", "title": title, "placeholder": placeholder, "tooltip": tooltip, **extra},
            )

        return {
            "required": {
                "seeds": ("INT", {"forceInput": True, "tooltip": "Seed list; one image per seed."}),
                "start_index": (
                    "INT",
                    {"default": 1, "min": 1, "max": MAX_INDEX, "tooltip": "Line to generate (1-based). Advances automatically."},
                ),
                "end_index": (
                    "INT",
                    {"default": 0, "min": 0, "max": MAX_INDEX, "tooltip": "Last line to generate (inclusive). 0 = last line of the lists."},
                ),
                "batch": (
                    "INT",
                    {"default": 4, "min": 1, "max": 1024, "tooltip": "Images per line (uses the first N seeds)."},
                ),
                "auto_advance": (
                    "BOOLEAN",
                    {"default": True, "tooltip": "Queue the next line automatically after a successful run."},
                ),
                "prepend": text("Prepend", TEXT, "Fixed text before every prompt (style, artist tags)."),
                "append": text("Append", TEXT, "Fixed text after every prompt (quality tags)."),
                "booru": text("Booru tags", MULTILINE_TEXT, "One booru tag line per prompt."),
                "natural": text("Natural language", MULTILINE_TEXT, "One natural-language line per prompt."),
                "character_booleans": text(
                    "Character keywords",
                    MULTILINE_TEXT,
                    "One keyword line per prompt, for example 'nohead, nobottom'. Keywords: nohair nohead "
                    "noeyes noface nochest notop nobottom nolegs nofeet. Listed parts are dropped for that line.",
                ),
            },
            "optional": {
                "character": ("STRING", {"forceInput": True, "tooltip": "From Character Definition."}),
                "width": text(
                    "W",
                    MULTILINE_INT,
                    f"Latent width per prompt line, in pixels. Empty = {DEFAULT_SIZE}.",
                    group="latent_size",
                    group_title="Latent size",
                ),
                "height": text(
                    "H",
                    MULTILINE_INT,
                    f"Latent height per prompt line, in pixels. Empty = {DEFAULT_SIZE}.",
                    group="latent_size",
                    group_title="Latent size",
                ),
            },
        }

    def build(self, seeds, start_index, end_index, batch, auto_advance, prepend, append, booru, natural,
              character_booleans, character=None, width=None, height=None):
        result = build_batch(
            start_index=_first(start_index, 1),
            end_index=_first(end_index, 0),
            batch=_first(batch, 1),
            prepend=_first(prepend, ""),
            append=_first(append, ""),
            booru=_first(booru, ""),
            natural=_first(natural, ""),
            character_booleans=_first(character_booleans, ""),
            character=_first(character),
            seeds=seeds if isinstance(seeds, list) else [seeds],
            auto_advance=_first(auto_advance, True),
            width=_first(width, ""),
            height=_first(height, ""),
        )
        for warning in result.warnings:
            log.warning("[Batch Prompt Builder] %s", warning)

        prompts, out_seeds = result.prompts, result.seeds
        if result.done:
            log.info("[Batch Prompt Builder] %s", result.status)
            latent = None
            if ExecutionBlocker is not None:
                latent = ExecutionBlocker(None)
                prompts, out_seeds = [latent], [latent]
        else:
            latent = empty_latent(result.width, result.height)

        return {
            "ui": {
                "bp_advance": [result.advance],
                "bp_next_index": [result.next_index],
                "bp_status": [result.status],
            },
            "result": (prompts, out_seeds, result.template, result.status, latent),
        }
