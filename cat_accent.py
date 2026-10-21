"""Cat accent: respell text the way a cat-mouthed speaker would say it, before Chatterbox.

The rules follow what is known about cat vocal anatomy (see the project's "How a Sentient Cat
Would Pronounce English" research): cats already make m, w, k, glottal catches, rolled trills
and hisses, but their small, stiff lips cannot seal for p and b or tuck under the teeth for
f and v. Vowels are long and gliding.

Three strengths, each adding to the one before:
* light: commas become "...", vowel-initial words get a glottal catch ('), long vowels are held
  (moon -> mooon), r is rolled (rr), f/ph -> h, v -> w.
* medium (default): also b -> m, p -> m at the start of a word and a catch (') inside it,
  and one hiss "sh" for s, z, sh, ch, j and soft c.
* strong: also th -> d at the start of a word (s elsewhere) and l -> w.

Example (medium): "Hello there little one, the moon is out tonight, and the fish are sleeping in the river."
-> "Hello therre little 'one... the mooon 'ish 'ouut tonight... 'and the hish 'arre shleee'ing 'in the rriwerr."

Cat words (meow, mew, purr, mrrp, prrr, nya) are left as they are.
"""

import re

STRENGTHS = ("light", "medium", "strong")

# Expanded first so their periods are not treated as sentence ends.
TITLES = [
    (re.compile(r"\bMrs\.?(?=\s|$)"), "Missus"),
    (re.compile(r"\bmrs\.?(?=\s|$)", re.I), "missus"),
    (re.compile(r"\bMr\.?(?=\s|$)"), "Mister"),
    (re.compile(r"\bmr\.?(?=\s|$)", re.I), "mister"),
    (re.compile(r"\bMs\.(?=\s|$)"), "Miz"),
    (re.compile(r"\bDr\.(?=\s|$)"), "Doctor"),
]

# Words cats already "say" stay untouched.
CAT_WORDS = re.compile(r"(?:m+e*o+w+|mi+a+o+w+|me+w+|mr+[aeiou]*[pw]+|mr+o*w+|pu+r+|pr+|nya+n*)", re.I)

WORD = re.compile(r"[A-Za-z]+")
VOWELS = "aeiou"
LONG_VOWELS = re.compile(r"oo|ee|ou|ea|oa|ai")
HISS = re.compile(r"tch|sh|ch|ss|s|z|j|c(?=[ei])")


def _hold_vowels(word):
    """oo -> ooo, ee -> eee, ou -> ouu ... never more than three of one letter."""
    def hold(m):
        nxt = m.string[m.end():m.end() + 1]
        return m.group(0) if nxt == m.group(0)[-1] else m.group(0) + m.group(0)[-1]

    return LONG_VOWELS.sub(hold, word)


def _l_to_w(word):
    """l -> w, except right after a consonant cluster at the start ("sleep" keeps its sl)."""
    out = []
    for i, c in enumerate(word):
        if c == "l" and not (i > 0 and all(ch not in VOWELS for ch in word[:i])):
            c = "w"
        out.append(c)
    return "".join(out)


def _respell(word, level):
    w = word.lower()
    w = _hold_vowels(w)
    w = re.sub(r"(?<!r)r(?!r)", "rr", w)  # rolled, like the chirrup
    w = w.replace("ph", "h").replace("f", "h").replace("v", "w")  # lips can't reach the teeth
    if level >= 1:
        w = w.replace("b", "m")
        w = re.sub(r"mp|pp", "m", w)
        w = re.sub(r"^p", "m", w)
        w = w.replace("p", "'")  # a catch where the lips would have sealed
        w = HISS.sub("sh", w)
    if level >= 2:
        w = re.sub(r"^th", "d", w).replace("th", "s")
        w = _l_to_w(w)
    return w


def _restore_case(original, new):
    if len(original) > 1 and original.isupper():
        return new.upper()
    if original[0].isupper():
        return new[:1].upper() + new[1:]
    return new


def cat_accent(text, strength="medium"):
    """Return text respelled with the cat accent. Line breaks are kept."""
    level = STRENGTHS.index(strength)
    lines = []
    for line in text.split("\n"):
        for pattern, title in TITLES:
            line = pattern.sub(title, line)

        def word(m):
            original = m.group(0)
            if CAT_WORDS.fullmatch(original):
                return original
            return _restore_case(original, _respell(original, level))

        line = WORD.sub(word, line)
        # Glottal catch before a vowel-initial word, except the first word of a sentence.
        line = re.sub(r"(^|[.!?]\s+|\s+)([aeiouAEIOU])",
                      lambda m: m.group(1) + ("'" if m.group(1).isspace() else "") + m.group(2), line)
        line = re.sub(r"(?<=[A-Za-z])\s*[,;]", "...", line)
        lines.append(re.sub(r"[ \t]{2,}", " ", line))
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Preview the cat accent")
    parser.add_argument("text", nargs="+")
    parser.add_argument("--strength", choices=STRENGTHS, default="medium")
    args = parser.parse_args()
    print(cat_accent(" ".join(args.text), args.strength))
