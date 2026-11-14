from .nodes.batch_prompt_builder import BatchPromptBuilder
from .nodes.character_definition import CharacterDefinition
from .nodes.seed_list import SeedList

NODE_CLASS_MAPPINGS = {
    "BatchPrompt_CharacterDefinition": CharacterDefinition,
    "BatchPrompt_Builder": BatchPromptBuilder,
    "BatchPrompt_SeedList": SeedList,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BatchPrompt_CharacterDefinition": "Character Definition",
    "BatchPrompt_Builder": "Batch Prompt Builder",
    "BatchPrompt_SeedList": "Seed List",
}

WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
