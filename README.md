# comfyui-batch-builder

ComfyUI custom nodes for batch prompting: walk through a list of prompt lines and generate several seeded, wildcard-varied images per line, one queue run per line.

- **Before:** one prompt with wildcards and a seed list gives X variations in one run.
- **After:** Y prompt lines give X variations of each line, over Y runs, queued automatically.

## Nodes

All three are under `prompt/batch`.

### Character Definition

One character split into parts, each with an on/off switch:

| Part | Drop keyword |
| --- | --- |
| Base (name, series, skin, body type) | none |
| Hair | `nohair` |
| Head (hat, ahoge, ...) | `nohead` |
| Eyes | `noeyes` |
| Face (mask, mole, freckles, ...) | `noface` |
| Chest | `nochest` |
| Top | `notop` |
| Bottom | `nobottom` |
| Legs | `nolegs` |
| Feet | `nofeet` |

Outputs:

- **Character**: structured string for Batch Prompt Builder.
- **Preview**: enabled parts joined with `, `.

Trailing commas in the fields are not needed; parts are trimmed and joined automatically.

### Seed List

Makes **Total** seeds from one master seed (**Method** `random`, `increment` or `decrement`, between **Min num** and **Max num**).

The master seed is chosen when the prompt is queued, like KSampler (Efficient), and ignores ComfyUI's "control before/after generate" setting:

- **Seed** = `-1` picks a new master seed on every queue. The workflow saved with the images contains the real seed, not `-1`.
- **Randomize / Last Queued Seed** switches between `-1` and the newest queued seed.
- The row below shows the last four queued master seeds. Click one to pin it.
- Right-click the node for **Seed behavior**: `Randomize`, `Increment` or `Decrement` the master seed from the last one while **Seed** is `-1`.

Outputs:

- **Seeds** is a list, so every node it feeds runs once per seed.
- **Preview** shows the seeds as text.
- **Total** is the seed count.

### Batch Prompt Builder

Builds the prompt for line **Start index**, makes one variant per seed, then queues the next line.

Text fields are labeled and can be rolled up: click a label to roll or unroll it, and drag a field's bottom edge to resize it on its own. A rolled field shows a preview of its first line. Character Definition fields work the same way, with each part's on/off switch on its label row. These fields are typed in on the node; they do not accept a STRING link from another node.

The grey placeholder names the data type: `text` is one block of text, `multiline text` is one string per prompt line, and `multiline int` is one integer per prompt line.

| Widget | Meaning |
| --- | --- |
| **Start index** | Line to generate, 1-based. Advances automatically. |
| **End index** | Last line to generate, inclusive. `0` means the last line of the lists. |
| **Batch** | Images per line. Uses the first **Batch** seeds; if there are fewer seeds than **Batch**, they repeat in order (4 seeds, batch 6: 1 2 3 4 1 2). |
| **Prompt order** | `language first` (default) or `tag first`. See Prompt order below. |
| **Vary wildcards** | Off by default. When on, a seed that repeats in the batch gets a new wildcard roll each time (see Wildcards). |
| **Auto advance** | Queue the next line after a successful run. |
| **Prepend** / **Append** | Fixed text around every prompt (style, artist, quality tags). |
| **Booru tags** | One booru tag line per prompt. |
| **Natural language** | One natural-language line per prompt. |
| **Character keywords** | One keyword line per prompt, for example `nohead, noeyes, nobottom`. |
| **Latent size** `W` / `H` | One width and one height per prompt line, side by side under one header. |

**Prompt order.** **Prepend** is always first and **Append** always last. The character and the booru line are one tag group, character first.

- `language first`: Prepend, natural language, character, booru line, Append.
- `tag first`: Prepend, character, booru line, natural language, Append.

```text
language first: masterpiece, she stands in the rain. 1girl, miku, outdoors, artist,
tag first:      masterpiece, 1girl, miku, outdoors, she stands in the rain. artist,
```

**Punctuation and spaces.** Every block is cleaned before it is joined, so you don't need to type separators:

- Tag fields (Prepend, Append, booru lines, character parts) become `tag, tag, `: one comma and one space between tags, extra spaces and empty tags removed. A line break in Prepend or Append counts as a comma. Commas inside a `{...}` wildcard do not split it.
- Natural language becomes `Sentence. Sentence. `: spaces collapsed, one space after each `.`, `!` or `?`, and a period added at the end when missing. Decimals, weights like `(word:1.2)` and `...` are left alone.
- After wildcards are picked, gaps left by an empty option (`, ,`, doubled spaces or periods) are removed.

**Lines.** Booru and natural are read line by line together. Blank lines count, so line numbers stay stable. If both lists have content and their lengths differ, the shorter one is padded with empty lines and a warning is shown.

**Character keywords.** A part is included when it has text, its switch is on in Character Definition, and the current **Character keywords** line does not contain its drop keyword. Keywords are whole words, case-sensitive. An empty keyword line uses the switches alone. Unknown keywords are reported as warnings.

**Latent size.** Each prompt line gets its own width and height, read from the same line number as the prompt. All **Batch** images of that line share the size. A list shorter than the prompts reuses its last value; an empty list or a line that is not a positive integer uses 1024. Values that are not multiples of 8 are rounded down to one (minimum 64). Each of these cases shows a warning in **Status**.

**Wildcards.** `{red hair|blonde hair|{short|long} black hair}` is resolved once per seed, so the same seed always gives the same prompt and matches the KSampler seed. Use `\{`, `\}` and `\|` for literal characters. Impact `__file__` wildcards are not supported.

To test wildcard variations on a single sampler seed, set Seed List **Total** to 1, **Batch** to 4 and turn on **Vary wildcards**. KSampler gets the same seed four times; the first prompt is the one that seed always gives, and the other three use different, repeatable wildcard rolls. Distinct seeds are unaffected. Wildcards resolved by other nodes from the **Seeds** output (such as a negative wildcard processor) still see only the sampler seed and do not vary.

Outputs:

- **Prompts**: one resolved prompt per seed (list).
- **Seeds**: the seeds actually used (list).
- **Template**: the line before wildcard resolution.
- **Status**: current line, variant count, latent size, dropped parts and warnings. Connect a text display node to watch progress.
- **Batch**: the number of images for this line (a single integer). Connect it to a second Seed List's **Total** so a hires pass makes the same number of seeds.
- **Latent**: an empty latent (batch size 1) at the line's width and height. Connect it to KSampler `latent_image` in place of Empty Latent Image.

## Wiring

```mermaid
flowchart LR
  charDef[Character Definition] -->|Character| builder[Batch Prompt Builder]
  seedList[Seed List] -->|Seeds| builder
  builder -->|Prompts| posEncode[CLIP Text Encode positive]
  builder -->|Seeds| sampler[KSampler seed]
  builder -->|Latent| sampler
  builder -->|Seeds| negWildcard[Negative wildcard processor]
  posEncode --> sampler
```

- Connect KSampler and the negative wildcard processor to the **builder's** **Seeds** output, not to the Seed List directly. That keeps prompt i, negative i and sampler seed i aligned, and stops the run cleanly after the last line.
- If a hires pass uses its own seeds, give it a second Seed List and connect the builder's **Batch** output to its **Total**, so both passes always have the same number of seeds.
- Queue with **batch count 1**. The browser extension queues each next line itself.

Auto-advance runs in the ComfyUI browser tab: it listens for the finished run, sets **Start index** to the next line and queues again. It stops at **End index**, at the end of the lists, on an error, or when you cancel. Prompts queued only through the API do not advance.

## Install

### Local ComfyUI

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/ThedDryz/comfyui-batch-builder.git
```

Restart ComfyUI. No extra Python dependencies.

## Tests

```bash
python -m unittest discover -s tests
```
