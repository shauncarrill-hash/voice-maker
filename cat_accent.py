"""Cat accent: respell text the way a cat-mouthed speaker would say it, before Chatterbox.

A cat's lips don't close and its mouth is shaped differently, so:
* lip sounds move forward in the mouth (p->t, b->d, m->n, w->y, v->z, word-initial f->sh),
* vowel pairs are drawn out by repeating the last vowel ("moon" -> "nooon"),
* words starting with a vowel get a glottal catch (’),
* commas become trailing pauses ("...").

Example: "Hello there little one, the moon is out tonight, and the fish are sleeping in the river."
-> "Hello there little ’one... the nooon ’is ’ouut tonight... ’and the shish ’are sleeeting ’in the rizer."

Same rules as the Cat Translator app (cat-translator/src/translate.js).
"""

import re

SOUND_STYLES = {
    # Plain pauses only.
    "off": {",": "...", ".": ".", "!": "!"},
    # Cat noises spoken at the punctuation.
    "spoken": {",": "... mrrr—", ".": ". prrr.", "!": "! mrrrow!"},
}

# Expanded first so their periods are not treated as sentence ends.
TITLES = [
    (re.compile(r"\bMrs\.?(?=\s|$)"), "Missus"),
    (re.compile(r"\bmrs\.?(?=\s|$)", re.I), "missus"),
    (re.compile(r"\bMr\.?(?=\s|$)"), "Mister"),
    (re.compile(r"\bmr\.?(?=\s|$)", re.I), "mister"),
    (re.compile(r"\bMs\.(?=\s|$)"), "Miz"),
    (re.compile(r"\bDr\.(?=\s|$)"), "Doctor"),
]

# Cat words are already cat-shaped, so they are left alone ("meow" must not become "neooy").
CAT_WORDS = re.compile(r"\b(?:m+e*o+w+|mi+a+o+w+|me+w+|mr+[aeiou]*[pw]+|mr+o*w+|pu+r+|pr+|nya+n*)\b", re.I)

# Lips don't close: bilabials and labiodentals move forward in the mouth.
LETTER_SHIFTS = {"p": "t", "b": "d", "m": "n", "w": "y", "v": "z"}


def _shift_letters(text):
    def swap(match):
        c = match.group(0)
        out = LETTER_SHIFTS[c.lower()]
        return out.upper() if c.isupper() else out

    text = re.sub(r"[pbmwv]", swap, text, flags=re.I)
    text = re.sub(r"\bf", "sh", text)
    return re.sub(r"\bF", "Sh", text)


def _stretch_vowels(text):
    """Vowel clusters get drawn out by repeating their last vowel ("you" -> "youu")."""
    return re.sub(r"[aeiou]{2,}", lambda m: m.group(0) + m.group(0)[-1].lower(), text, flags=re.I)


def _add_glottal(text):
    """Glottal attack before word-initial vowels."""
    return re.sub(r"\b(?<!['’])([aeiou])", r"’\1", text, flags=re.I)


def _punctuate(text, sounds):
    """One pass over punctuation so inserted markers are never re-processed."""
    style = SOUND_STYLES.get(sounds, SOUND_STYLES["off"])

    def mark(match):
        p = match.group(0)
        if p == "?":
            return "...?"
        return style.get(p, p)  # an existing ellipsis stays a plain pause

    return re.sub(r"\.{3}|…|[,!?]|\.(?!\d)", mark, text)


def cat_accent(text, sounds="off", stretch=True, glottal=True):
    """Return text respelled with the cat accent. Line breaks are kept."""
    lines = []
    for line in text.split("\n"):
        kept = []
        line = CAT_WORDS.sub(lambda m: kept.append(m.group(0)) or f"\x00{len(kept) - 1}\x00", line)
        for pattern, word in TITLES:
            line = pattern.sub(word, line)
        line = _shift_letters(line)
        if stretch:
            line = _stretch_vowels(line)
        if glottal:
            line = _add_glottal(line)
        line = _punctuate(line, sounds)
        line = re.sub(r"\x00(\d+)\x00", lambda m: kept[int(m.group(1))], line)
        lines.append(re.sub(r"[ \t]{2,}", " ", line))
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    print(cat_accent(" ".join(sys.argv[1:]) or sys.stdin.read()))
