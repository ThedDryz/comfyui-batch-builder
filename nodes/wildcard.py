"""Seeded resolver for `{a|b|c}` wildcards, including nested groups.

`\\{`, `\\}` and `\\|` produce literal characters. Any other backslash is kept
as-is so prompt escapes like `\\(artist\\)` pass through untouched. An unclosed
`{` is kept literally and reported.
"""

import random

ESCAPABLE = "{}|"


class Group:
    __slots__ = ("options",)

    def __init__(self, options):
        self.options = options


class Template:
    def __init__(self, nodes, errors):
        self.nodes = nodes
        self.errors = errors

    @property
    def has_wildcards(self):
        return any(isinstance(n, Group) for n in self.nodes)

    def resolve(self, seed):
        rng = random.Random(seed)
        out = []
        _render(self.nodes, rng, out)
        return "".join(out)


def parse(text):
    parser = _Parser(text)
    try:
        nodes, _ = parser.seq(0, False)
    except RecursionError:
        return Template([text] if text else [], ["wildcards nested too deeply; text left unresolved"])
    errors = [f"unclosed '{{' at character {pos + 1}" for pos in sorted(parser.unclosed)]
    return Template(nodes, errors)


def resolve(text, seed):
    return parse(text).resolve(seed)


class _Parser:
    def __init__(self, text):
        self.text = text
        self.unclosed = set()
        # A group parse depends only on its start position; caching keeps
        # runs of unclosed braces linear instead of exponential.
        self.groups = {}

    def seq(self, pos, in_group):
        text = self.text
        nodes = []
        buf = []
        length = len(text)
        while pos < length:
            c = text[pos]
            if c == "\\" and pos + 1 < length and text[pos + 1] in ESCAPABLE:
                buf.append(text[pos + 1])
                pos += 2
                continue
            if c == "{":
                group, end = self.group(pos + 1)
                if group is None:
                    self.unclosed.add(pos)
                    buf.append(c)
                    pos += 1
                    continue
                if buf:
                    nodes.append("".join(buf))
                    buf = []
                nodes.append(group)
                pos = end
                continue
            if in_group and c in "|}":
                break
            buf.append(c)
            pos += 1
        if buf:
            nodes.append("".join(buf))
        return nodes, pos

    def group(self, start):
        if start in self.groups:
            return self.groups[start]
        options = []
        pos = start
        result = None
        while True:
            seq, pos = self.seq(pos, True)
            options.append(seq)
            if pos >= len(self.text):
                result = (None, pos)
                break
            if self.text[pos] == "|":
                pos += 1
                continue
            result = (Group(options), pos + 1)
            break
        self.groups[start] = result
        return result


def _render(nodes, rng, out):
    for node in nodes:
        if isinstance(node, Group):
            _render(rng.choice(node.options), rng, out)
        else:
            out.append(node)
