import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nodes import wildcard
from nodes.batch_prompt_builder import BatchPromptBuilder, _roll_seed, build_batch
from nodes.character_definition import CharacterDefinition
from nodes.prompt_format import clean_prompt, format_sentences, format_tags
from nodes.seed_list import SeedList, make_seeds

SEEDS = [11, 22, 33, 44]


def character(**overrides):
    values = {
        "base": "1girl, gyaru,",
        "hair": "black hair",
        "head": "ahoge",
        "eyes": "red eyes",
        "face": "mole",
        "chest": "flat chest, ",
        "top": "hoodie",
        "bottom": "skirt",
        "legs": "thighhighs",
        "feet": "sneakers",
    }
    values.update(overrides)
    return CharacterDefinition().define(**values)[0]


class CharacterDefinitionTest(unittest.TestCase):
    def test_json_and_preview(self):
        char_json, preview = CharacterDefinition().define(base="1girl, ", hair="black hair", hair_enabled=True,
                                                          eyes="red eyes", eyes_enabled=False)
        parts = json.loads(char_json)["parts"]
        self.assertEqual(len(parts), 10)
        self.assertFalse(parts["eyes"]["enabled"])
        self.assertEqual(preview, "1girl, black hair")


class LineTest(unittest.TestCase):
    def test_zips_lines_in_order(self):
        r = build_batch(2, 0, 1, prepend="style,", append="quality", booru="b1\nb2\nb3",
                        natural="n1\nn2\nn3", character=character(), seeds=SEEDS)
        self.assertTrue(r.template.startswith("style, n2. 1girl, gyaru, black hair"))
        self.assertTrue(r.template.endswith("sneakers, b2, quality,"))
        self.assertEqual(r.warnings, [])

    def test_trailing_newline_is_not_a_line(self):
        r = build_batch(1, 0, 1, booru="b1\nb2\n", seeds=SEEDS)
        self.assertEqual(r.last_line, 2)

    def test_blank_lines_keep_numbering(self):
        r = build_batch(3, 0, 1, booru="b1\n\nb3", natural="n1\nn2\nn3", seeds=SEEDS)
        self.assertEqual(r.template, "n3. b3,")
        r = build_batch(2, 0, 1, booru="b1\n\nb3", natural="n1\nn2\nn3", seeds=SEEDS)
        self.assertEqual(r.template, "n2.")

    def test_length_mismatch_warns_and_pads(self):
        r = build_batch(3, 0, 1, booru="b1\nb2\nb3", natural="n1", seeds=SEEDS)
        self.assertEqual(r.template, "b3,")
        self.assertEqual(r.last_line, 3)
        self.assertIn("padded", r.warnings[0])

    def test_single_list_does_not_warn(self):
        r = build_batch(1, 0, 1, booru="b1\nb2", seeds=SEEDS)
        self.assertEqual(r.warnings, [])

    def test_empty_lists_make_one_line(self):
        r = build_batch(1, 0, 2, prepend="style", seeds=SEEDS)
        self.assertEqual(r.prompts, ["style,", "style,"])
        self.assertFalse(r.advance)


class PromptOrderTest(unittest.TestCase):
    ARGS = dict(prepend="masterpiece", append="artist", booru="outdoors", natural="she stands in the rain",
                character="1girl, miku", seeds=SEEDS)

    def test_language_first_is_default(self):
        r = build_batch(1, 0, 1, **self.ARGS)
        self.assertEqual(r.template, "masterpiece, she stands in the rain. 1girl, miku, outdoors, artist,")

    def test_tag_first(self):
        r = build_batch(1, 0, 1, prompt_order="tag first", **self.ARGS)
        self.assertEqual(r.template, "masterpiece, 1girl, miku, outdoors, she stands in the rain. artist,")

    def test_node_passes_order(self):
        with mock.patch("nodes.batch_prompt_builder.empty_latent", return_value=None):
            out = BatchPromptBuilder().build(
                seeds=SEEDS, start_index=[1], end_index=[0], batch=[1], auto_advance=[False],
                prepend=[""], append=[""], booru=["a"], natural=["n"], character_booleans=[""],
                prompt_order=["tag first"],
            )
        self.assertEqual(out["result"][2], "a, n.")


class PromptFormatTest(unittest.TestCase):
    def test_tags_get_comma_space(self):
        self.assertEqual(format_tags("  masterpiece ,best   quality,, \n score_9 "),
                         "masterpiece, best quality, score_9, ")
        self.assertEqual(format_tags(" , "), "")

    def test_wildcard_with_comma_stays_one_tag(self):
        self.assertEqual(format_tags("{red hair , long|blonde}  ,  smile"), "{red hair, long|blonde}, smile, ")

    def test_sentences_get_period_space(self):
        self.assertEqual(format_sentences("she  stands in the rain .she smiles  ,"),
                         "she stands in the rain. she smiles. ")
        self.assertEqual(format_sentences("Wow!"), "Wow! ")
        self.assertEqual(format_sentences("   "), "")

    def test_sentences_keep_decimals_weights_and_ellipses(self):
        self.assertEqual(format_sentences("A cat.Weight (x:1.2) and 3.5 cups... wow"),
                         "A cat. Weight (x:1.2) and 3.5 cups... wow. ")

    def test_resolved_prompt_is_cleaned(self):
        self.assertEqual(clean_prompt("a, , b ,  c"), "a, b, c")
        self.assertEqual(clean_prompt("she runs.. b,"), "she runs. b,")
        self.assertEqual(clean_prompt("she runs., b,"), "she runs. b,")
        self.assertEqual(clean_prompt("a, !?, b,"), "a, !?, b,")

    def test_empty_wildcard_option_leaves_no_gap(self):
        r = build_batch(1, 0, 4, booru="{a|}, b", natural="she {runs.|walks}", seeds=SEEDS)
        for prompt in r.prompts:
            self.assertNotIn("  ", prompt)
            self.assertNotIn(", ,", prompt)
            self.assertNotIn(".,", prompt)
            self.assertNotIn("..", prompt)


class KeywordTest(unittest.TestCase):
    def test_keywords_drop_parts(self):
        r = build_batch(1, 0, 1, booru="portrait", character_booleans="nohead, noeyes, nobottom, nolegs, nofeet",
                        character=character(), seeds=SEEDS)
        self.assertEqual(r.dropped, ["Head", "Eyes", "Bottom", "Legs", "Feet"])
        self.assertEqual(r.template, "1girl, gyaru, black hair, mole, flat chest, hoodie, portrait,")

    def test_switch_off_stays_off(self):
        r = build_batch(1, 0, 1, character_booleans="nohead", character=character(top_enabled=False),
                        seeds=SEEDS)
        self.assertNotIn("hoodie", r.template)
        self.assertNotIn("ahoge", r.template)
        self.assertIn("skirt", r.template)

    def test_empty_keyword_line_uses_switches(self):
        r = build_batch(2, 0, 1, booru="a\nb", character_booleans="nohair\n",
                        character=character(feet_enabled=False), seeds=SEEDS)
        self.assertIn("black hair", r.template)
        self.assertNotIn("sneakers", r.template)

    def test_keywords_are_whole_tokens(self):
        r = build_batch(1, 0, 1, booru="nohair", character_booleans="nohairs noup", character=character(),
                        seeds=SEEDS)
        self.assertIn("black hair", r.template)
        self.assertIn("unknown keyword(s) on line 1: nohairs, noup", r.warnings)

    def test_short_keyword_list_warns(self):
        r = build_batch(2, 0, 1, booru="a\nb\nc", character_booleans="nohair", character=character(),
                        seeds=SEEDS)
        self.assertIn("black hair", r.template)
        self.assertTrue(any("character booleans" in w for w in r.warnings))

    def test_plain_character_string_is_used_as_is(self):
        r = build_batch(1, 0, 1, booru="a", character="1boy", seeds=SEEDS)
        self.assertEqual(r.template, "1boy, a,")


class SeedTest(unittest.TestCase):
    def test_uses_first_batch_seeds(self):
        r = build_batch(1, 0, 2, natural="{red|blue|green} hair", seeds=SEEDS)
        self.assertEqual(r.seeds, [11, 22])
        self.assertEqual(r.template, "{red|blue|green} hair.")
        self.assertEqual(r.prompts, [clean_prompt(wildcard.resolve(r.template, s)) for s in (11, 22)])
        self.assertEqual(r.warnings, [])

    def test_short_seed_list_cycles(self):
        r = build_batch(1, 0, 6, natural="{red|blue|green} hair", seeds=SEEDS)
        self.assertEqual(r.seeds, [11, 22, 33, 44, 11, 22])
        self.assertEqual(r.prompts[4], r.prompts[0])
        self.assertTrue(any("only 4 seed(s) are connected; seeds are cycled" in w for w in r.warnings))

    def test_vary_wildcards_rolls_repeated_seed(self):
        text = "{a|b|c|d|e|f|g|h} {i|j|k|l|m|n|o|p}"
        r = build_batch(1, 0, 4, natural=text, seeds=[7], vary_wildcards=True)
        self.assertEqual(r.seeds, [7, 7, 7, 7])
        self.assertEqual(r.prompts, [clean_prompt(wildcard.resolve(r.template, _roll_seed(7, n))) for n in range(4)])
        self.assertEqual(r.prompts[0], clean_prompt(wildcard.resolve(r.template, 7)))
        self.assertGreater(len(set(r.prompts)), 1)
        again = build_batch(1, 0, 4, natural=text, seeds=[7], vary_wildcards=True)
        self.assertEqual(again.prompts, r.prompts)

    def test_vary_wildcards_keeps_distinct_seeds(self):
        text = "{red|blue|green} hair"
        on = build_batch(1, 0, 4, natural=text, seeds=SEEDS, vary_wildcards=True)
        off = build_batch(1, 0, 4, natural=text, seeds=SEEDS)
        self.assertEqual(on.prompts, off.prompts)

    def test_roll_seed_never_returns_seed(self):
        for seed in (0, 1, 7, 2**64 - 1):
            for n in range(1, 50):
                self.assertNotEqual(_roll_seed(seed, n), seed)

    def test_no_seeds_raises(self):
        with self.assertRaises(ValueError):
            build_batch(1, 0, 1, booru="a", seeds=[])


class IndexTest(unittest.TestCase):
    def test_advances_until_end(self):
        lines = "\n".join(f"b{i}" for i in range(1, 6))
        r = build_batch(2, 3, 1, booru=lines, seeds=SEEDS)
        self.assertEqual((r.advance, r.next_index, r.last_line), (True, 3, 3))
        r = build_batch(3, 3, 1, booru=lines, seeds=SEEDS)
        self.assertFalse(r.advance)

    def test_end_zero_means_last_line(self):
        r = build_batch(1, 0, 1, booru="a\nb", seeds=SEEDS)
        self.assertEqual(r.last_line, 2)

    def test_end_past_lists_stops_at_lists(self):
        r = build_batch(2, 99, 1, booru="a\nb", seeds=SEEDS)
        self.assertFalse(r.advance)

    def test_past_end_is_done(self):
        r = build_batch(4, 0, 1, booru="a\nb", seeds=SEEDS)
        self.assertTrue(r.done)
        self.assertEqual(r.prompts, [])
        self.assertIn("past the last line", r.status)

    def test_auto_advance_off(self):
        r = build_batch(1, 0, 1, booru="a\nb", seeds=SEEDS, auto_advance=False)
        self.assertFalse(r.advance)


class SizeTest(unittest.TestCase):
    def test_picks_size_for_line(self):
        r = build_batch(2, 0, 1, booru="a\nb\nc", width="1216\n1024\n832", height="832\n1024\n1216", seeds=SEEDS)
        self.assertEqual((r.width, r.height), (1024, 1024))
        self.assertIn("1024x1024", r.status)
        self.assertEqual(r.warnings, [])

    def test_short_list_reuses_last_and_warns(self):
        r = build_batch(3, 0, 1, booru="a\nb\nc", width="1216\n832", height="1024", seeds=SEEDS)
        self.assertEqual((r.width, r.height), (832, 1024))
        self.assertTrue(any("width has 2 lines" in w for w in r.warnings))
        self.assertTrue(any("height has 1 lines" in w for w in r.warnings))

    def test_empty_lists_default(self):
        r = build_batch(1, 0, 1, booru="a", seeds=SEEDS)
        self.assertEqual((r.width, r.height), (1024, 1024))

    def test_bad_line_warns_and_defaults(self):
        r = build_batch(1, 0, 1, booru="a\nb", width="wide\n832", height="-5\n832", seeds=SEEDS)
        self.assertEqual((r.width, r.height), (1024, 1024))
        self.assertTrue(any("width on line 1 is not a positive integer" in w for w in r.warnings))
        self.assertTrue(any("height on line 1 is not a positive integer" in w for w in r.warnings))

    def test_snaps_to_multiple_of_8(self):
        r = build_batch(1, 0, 1, booru="a", width="1210", height="20", seeds=SEEDS)
        self.assertEqual((r.width, r.height), (1208, 64))
        self.assertIn("width 1210 on line 1 rounded to 1208 (multiple of 8)", r.warnings)

    def test_node_returns_latent_slot(self):
        slot = BatchPromptBuilder.RETURN_NAMES.index("latent")
        self.assertEqual(BatchPromptBuilder.RETURN_TYPES[slot], "LATENT")
        self.assertFalse(BatchPromptBuilder.OUTPUT_IS_LIST[slot])
        batch_slot = BatchPromptBuilder.RETURN_NAMES.index("batch")
        self.assertEqual(batch_slot, slot - 1)
        self.assertEqual(BatchPromptBuilder.RETURN_TYPES[batch_slot], "INT")
        self.assertFalse(BatchPromptBuilder.OUTPUT_IS_LIST[batch_slot])
        optional = BatchPromptBuilder.INPUT_TYPES()["optional"]
        self.assertEqual(optional["width"][1]["group"], optional["height"][1]["group"])

    def test_controls_follow_batch_in_order(self):
        spec = BatchPromptBuilder.INPUT_TYPES()
        self.assertEqual(list(spec["required"])[:7],
                         ["seeds", "start_index", "end_index", "batch", "prompt_order", "vary_wildcards", "auto_advance"])
        order = spec["required"]["prompt_order"]
        self.assertEqual(order[0], ["tag first", "language first"])
        self.assertEqual(order[1]["default"], "language first")
        self.assertFalse(spec["required"]["vary_wildcards"][1]["default"])
        self.assertNotIn("vary_wildcards", spec["optional"])


class PlaceholderTest(unittest.TestCase):
    def test_placeholders_name_the_type(self):
        spec = BatchPromptBuilder.INPUT_TYPES()
        fields = {**spec["required"], **spec["optional"]}
        placeholders = {k: v[1].get("placeholder") for k, v in fields.items() if v[0] == "ROLL_TEXT"}
        self.assertEqual(placeholders, {
            "prepend": "text",
            "append": "text",
            "booru": "multiline text",
            "natural": "multiline text",
            "character_booleans": "multiline text",
            "width": "multiline int",
            "height": "multiline int",
        })
        char = CharacterDefinition.INPUT_TYPES()["required"]
        self.assertTrue(all(v[1]["placeholder"] == "text" for v in char.values() if v[0] == "ROLL_TEXT"))


class WildcardTest(unittest.TestCase):
    def test_same_seed_same_result(self):
        text = "{a|b|c} {d|e|f} {g|h}"
        self.assertEqual(wildcard.resolve(text, 5), wildcard.resolve(text, 5))
        self.assertGreater(len({wildcard.resolve(text, s) for s in range(50)}), 1)

    def test_nested(self):
        results = {wildcard.resolve("{a|{b|c}|d}", s) for s in range(200)}
        self.assertEqual(results, {"a", "b", "c", "d"})

    def test_empty_option(self):
        self.assertEqual({wildcard.resolve("x{|y}", s) for s in range(100)}, {"x", "xy"})

    def test_escapes(self):
        self.assertEqual(wildcard.resolve(r"\{a\|b\} \(artist\)", 1), r"{a|b} \(artist\)")

    def test_unclosed_is_literal_and_reported(self):
        t = wildcard.parse("a {b|c")
        self.assertEqual(t.resolve(1), "a {b|c")
        self.assertEqual(t.errors, ["unclosed '{' at character 3"])

    def test_unclosed_outer_keeps_inner_group(self):
        results = {wildcard.resolve("{a|{b|c}", s) for s in range(100)}
        self.assertEqual(results, {"{a|b", "{a|c"})

    def test_many_unclosed_is_fast(self):
        t = wildcard.parse("{" * 200)
        self.assertEqual(len(t.errors), 200)

    def test_too_deep_is_left_unresolved(self):
        t = wildcard.parse("{" * 5000)
        self.assertEqual(t.resolve(1), "{" * 5000)
        self.assertIn("nested too deeply", t.errors[0])

    def test_builder_reports_unclosed(self):
        r = build_batch(1, 0, 1, booru="{a|b", seeds=SEEDS)
        self.assertTrue(any("unclosed" in w for w in r.warnings))


class SeedListTest(unittest.TestCase):
    def test_random_is_stable(self):
        a = make_seeds(123, 4)
        self.assertEqual(a, make_seeds(123, 4))
        self.assertNotEqual(a, make_seeds(124, 4))
        self.assertTrue(all(0 <= s <= 1125899906842624 for s in a))

    def test_increment_and_decrement(self):
        self.assertEqual(make_seeds(10, 3, "increment"), [10, 11, 12])
        self.assertEqual(make_seeds(10, 3, "decrement"), [10, 9, 8])

    def test_wraps_inside_range(self):
        self.assertEqual(make_seeds(1, 3, "decrement", 0, 9), [1, 0, 9])
        self.assertEqual(make_seeds(9, 2, "increment", 0, 9), [9, 0])

    def test_node_outputs(self):
        out = SeedList().generate(0, 100, "increment", 3, 5)
        seeds, preview, total = out["result"]
        self.assertEqual(seeds, [5, 6, 7])
        self.assertEqual(preview, "5, 6, 7")
        self.assertEqual(total, 3)
        self.assertEqual(out["ui"]["bp_master_seed"], [5])
        self.assertEqual(SeedList.OUTPUT_IS_LIST, (True, False, False))

    def test_randomize_seed_is_resolved(self):
        out = SeedList().generate(0, 1125899906842624, "increment", 2, -1)
        master = out["ui"]["bp_master_seed"][0]
        self.assertTrue(0 <= master <= 1125899906842624)
        self.assertEqual(out["result"][0], [master, master + 1])

    def test_randomize_seed_always_reruns(self):
        changed = SeedList.IS_CHANGED(seed=-1)
        self.assertNotEqual(changed, changed)
        self.assertEqual(SeedList.IS_CHANGED(seed=7), 7)

    def test_no_after_generate_control(self):
        seed_spec = SeedList.INPUT_TYPES()["required"]["seed"][1]
        self.assertFalse(seed_spec["control_after_generate"])
        self.assertEqual(seed_spec["default"], -1)


class NodeWrapperTest(unittest.TestCase):
    def test_unwraps_list_inputs(self):
        with mock.patch("nodes.batch_prompt_builder.empty_latent", side_effect=lambda w, h: (w, h)):
            out = BatchPromptBuilder().build(
                seeds=SEEDS, start_index=[1], end_index=[0], batch=[3], auto_advance=[True],
                prepend=["s"], append=[""], booru=["a\nb"], natural=[""], character_booleans=[""],
                character=[character()], width=["832\n1216"], height=["1216\n832"],
            )
        prompts, seeds, template, status, count, latent = out["result"]
        self.assertEqual(latent, (832, 1216))
        self.assertEqual(count, 3)
        self.assertEqual(len(prompts), 3)
        self.assertEqual(seeds, SEEDS[:3])
        self.assertTrue(template.startswith("s, 1girl"))
        self.assertTrue(template.endswith(", a,"))
        self.assertEqual(out["ui"]["bp_advance"], [True])
        self.assertEqual(out["ui"]["bp_next_index"], [2])
        self.assertIn("line 1 of 2", status)


if __name__ == "__main__":
    unittest.main()
