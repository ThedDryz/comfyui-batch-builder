import json

CATEGORY = "prompt/batch"

# Multiline text drawn by js/roll_field.js: labeled, roll/unroll, independently resizable.
ROLL_TEXT = "ROLL_TEXT"

# (key, label, drop keyword). Base has no drop keyword.
PARTS = (
    ("base", "Base", None),
    ("hair", "Hair", "nohair"),
    ("head", "Head", "nohead"),
    ("eyes", "Eyes", "noeyes"),
    ("face", "Face", "noface"),
    ("chest", "Chest", "nochest"),
    ("top", "Top", "notop"),
    ("bottom", "Bottom", "nobottom"),
    ("legs", "Legs", "nolegs"),
    ("feet", "Feet", "nofeet"),
)

# Placeholders name the data type; the label names the field.
TEXT = "text"
MULTILINE_TEXT = "multiline text"
MULTILINE_INT = "multiline int"

HINTS = {
    "base": "1girl, character name, series, skin tone, body type",
    "hair": "hair color and style",
    "head": "hat, cap, ahoge",
    "eyes": "eye color and shape",
    "face": "mask, mole, freckles",
    "chest": "breast shape",
    "top": "top clothes and style",
    "bottom": "bottom clothes and style",
    "legs": "legs shape, legwear",
    "feet": "shoes, feet details",
}

DROP_KEYWORDS = {keyword: key for key, _, keyword in PARTS if keyword}


def clean_part(text):
    return text.strip().strip(",").strip()


def join_parts(texts):
    return ", ".join(t for t in (clean_part(x) for x in texts) if t)


def build_character(values):
    parts = {}
    for key, _, _ in PARTS:
        parts[key] = {
            "text": values.get(key, "") or "",
            "enabled": bool(values.get(f"{key}_enabled", True)),
        }
    return {"version": 1, "parts": parts}


def preview(character):
    parts = character["parts"]
    return join_parts(parts[key]["text"] for key, _, _ in PARTS if parts[key]["enabled"])


class CharacterDefinition:
    CATEGORY = CATEGORY
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("character", "preview")
    FUNCTION = "define"
    DESCRIPTION = (
        "Character appearance split into parts. Connect `character` to Batch Prompt Builder, "
        "which can drop parts per line with keywords such as nohair or nobottom."
    )

    @classmethod
    def INPUT_TYPES(cls):
        required = {}
        for key, label, keyword in PARTS:
            tooltip = f"{label}: {HINTS[key]}." + (f" A keyword line containing '{keyword}' drops it." if keyword else "")
            required[key] = (
                ROLL_TEXT,
                {
                    "default": "",
                    "title": label,
                    "placeholder": TEXT,
                    "toggle": f"{key}_enabled",
                    "tooltip": tooltip,
                },
            )
            required[f"{key}_enabled"] = (
                "BOOLEAN",
                {"default": True, "label_on": "on", "label_off": "off", "tooltip": f"Include {label}."},
            )
        return {"required": required}

    def define(self, **kwargs):
        character = build_character(kwargs)
        return (json.dumps(character, ensure_ascii=False), preview(character))
