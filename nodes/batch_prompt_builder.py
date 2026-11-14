import json
import logging
import re
from dataclasses import dataclass, field

from . import wildcard
from .character_definition import DROP_KEYWORDS, PARTS, join_parts

try:
    from comfy_execution.graph import ExecutionBlocker
except ImportError:
    ExecutionBlocker = None

CATEGORY = "prompt/batch"
MAX_INDEX = 100000

log = logging.getLogger("BatchPrompt")


def split_lines(text):
    return text.splitlines() if text else []


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

    @property
    def status(self):
        if self.done:
            text = f"done: line {self.line} is past the last line {self.last_line}"
        else:
            text = f"line {self.line} of {self.last_line} | {len(self.prompts)} variant(s)"
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
):
    booru_lines = split_lines(booru)
    natural_lines = split_lines(natural)
    keyword_lines = split_lines(character_booleans)
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
    RETURN_TYPES = ("STRING", "INT", "STRING", "STRING")
    RETURN_NAMES = ("prompts", "seeds", "template", "status")
    OUTPUT_IS_LIST = (True, True, False, False)
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
        text = {"multiline": True, "default": "", "dynamicPrompts": False}
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
                "prepend": ("STRING", {**text, "tooltip": "Fixed text before every prompt (style, artists)."}),
                "append": ("STRING", {**text, "tooltip": "Fixed text after every prompt."}),
                "booru": ("STRING", {**text, "tooltip": "One booru tag line per prompt."}),
                "natural": ("STRING", {**text, "tooltip": "One natural-language line per prompt."}),
                "character_booleans": (
                    "STRING",
                    {
                        **text,
                        "tooltip": "One keyword line per prompt: nohair nohead noeyes noface nochest "
                        "notop nobottom nolegs nofeet. Listed parts are dropped for that line.",
                    },
                ),
            },
            "optional": {
                "character": ("STRING", {"forceInput": True, "tooltip": "From Character Definition."}),
            },
        }

    def build(self, seeds, start_index, end_index, batch, auto_advance, prepend, append, booru, natural,
              character_booleans, character=None):
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
        )
        for warning in result.warnings:
            log.warning("[Batch Prompt Builder] %s", warning)

        prompts, out_seeds = result.prompts, result.seeds
        if result.done:
            log.info("[Batch Prompt Builder] %s", result.status)
            if ExecutionBlocker is not None:
                prompts, out_seeds = [ExecutionBlocker(None)], [ExecutionBlocker(None)]

        return {
            "ui": {
                "bp_advance": [result.advance],
                "bp_next_index": [result.next_index],
                "bp_status": [result.status],
            },
            "result": (prompts, out_seeds, result.template, result.status),
        }
