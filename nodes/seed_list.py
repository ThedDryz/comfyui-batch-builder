import random

CATEGORY = "prompt/batch"

MAX_SEED = 0xFFFFFFFFFFFFFFFF
METHODS = ("random", "increment", "decrement")


def make_seeds(seed, total, method="random", min_num=0, max_num=1125899906842624):
    if max_num < min_num:
        min_num, max_num = max_num, min_num
    if method == "random":
        rng = random.Random(seed)
        return [rng.randint(min_num, max_num) for _ in range(total)]
    step = 1 if method == "increment" else -1
    span = max_num - min_num + 1
    # increment/decrement wrap inside [min_num, max_num] so every seed stays valid for KSampler.
    return [min_num + (seed - min_num + step * i) % span for i in range(total)]


class SeedList:
    CATEGORY = CATEGORY
    RETURN_TYPES = ("INT", "STRING", "INT")
    RETURN_NAMES = ("seeds", "preview", "total")
    OUTPUT_IS_LIST = (True, False, False)
    FUNCTION = "generate"
    DESCRIPTION = (
        "Generates `total` seeds from one master seed. `seeds` is a list, so every node it feeds "
        "runs once per seed (one image per seed)."
    )

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "min_num": ("INT", {"default": 0, "min": 0, "max": MAX_SEED}),
                "max_num": ("INT", {"default": 1125899906842624, "min": 0, "max": MAX_SEED}),
                "method": (list(METHODS), {"default": "random"}),
                "total": ("INT", {"default": 4, "min": 1, "max": 1024}),
                "seed": ("INT", {"default": 0, "min": 0, "max": MAX_SEED, "control_after_generate": True}),
            }
        }

    def generate(self, min_num, max_num, method, total, seed):
        seeds = make_seeds(seed, total, method, min_num, max_num)
        return (seeds, ", ".join(str(s) for s in seeds), len(seeds))
