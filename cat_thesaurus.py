"""Cat thesaurus: swap words a cat's mouth would struggle with for ones it can say.

Uses the same anatomy as cat_accent.py: small, stiff lips can't seal for p and b or reach the
teeth for f and v, and th is awkward too. Each word is scored by those sounds, and a word in the
list below is replaced by its easiest alternative when that one is easier ("sleep" -> "doze",
"traveler" -> "wanderer"). Words not in the list are left alone, so the meaning stays put.

Run "python cat_thesaurus.py your text" to see what would change.
"""

import re

# Hard sounds for a cat and how much each costs. Letters count once per occurrence.
HARD = [("ph", 2.0), ("th", 1.0), ("p", 2.0), ("b", 2.0), ("f", 2.0), ("v", 2.0)]

# word -> alternatives. Only plain synonyms that fit wherever the word does, so swapping one in
# keeps the sentence's meaning (no "have" -> "own": "I have to go" would break).
SYNONYMS = {
    "afraid": ["scared", "alarmed"],
    "baby": ["little one", "infant"],
    "bad": ["wicked", "nasty", "rotten"],
    "battle": ["clash", "war"],
    "beautiful": ["lovely", "gorgeous", "stunning"],
    "because": ["since", "as"],
    "begin": ["start", "commence"],
    "believe": ["think", "trust"],
    "beside": ["next to", "near"],
    "best": ["greatest", "finest"],
    "between": ["among", "amid"],
    "beware": ["take care", "watch out"],
    "big": ["large", "huge", "giant", "great"],
    "blood": ["gore"],
    "brave": ["daring", "bold"],
    "break": ["crack", "smash", "shatter"],
    "bright": ["shining", "gleaming", "radiant"],
    "bring": ["carry", "fetch"],
    "brother": ["kin", "sibling"],
    "build": ["make", "create"],
    "but": ["yet", "though"],
    "buy": ["get", "acquire"],
    "captain": ["commander", "chief"],
    "evil": ["wicked", "cruel"],
    "explore": ["roam", "scout"],
    "fast": ["quick", "swift"],
    "father": ["dad"],
    "favorite": ["darling", "dearest"],
    "favourite": ["darling", "dearest"],
    "fear": ["dread", "terror"],
    "feel": ["sense"],
    "fight": ["clash", "struggle", "combat"],
    "find": ["seek", "locate"],
    "fine": ["okay", "alright", "well"],
    "finish": ["end", "complete"],
    "first": ["earliest", "initial"],
    "fly": ["soar", "glide"],
    "food": ["meal", "chow", "eats"],
    "fool": ["idiot", "dunce"],
    "forest": ["woods", "woodland"],
    "friend": ["mate", "ally", "comrade"],
    "full": ["sated", "stuffed"],
    "funny": ["silly", "comic"],
    "future": ["tomorrow", "days to come"],
    "goodbye": ["so long", "farewell"],
    "happy": ["glad", "merry", "content"],
    "hope": ["wish", "trust"],
    "live": ["dwell", "reside"],
    "love": ["adore", "cherish"],
    "mother": ["mom", "mama"],
    "never": ["at no time"],
    "people": ["humans", "folk"],
    "perfect": ["ideal", "flawless"],
    "person": ["human", "one"],
    "place": ["area", "site", "spot"],
    "plan": ["scheme", "idea"],
    "planet": ["world"],
    "please": ["kindly"],
    "poor": ["needy"],
    "power": ["might", "strength"],
    "prepare": ["get ready", "ready"],
    "pretty": ["lovely", "cute", "nice"],
    "price": ["cost"],
    "probably": ["likely"],
    "problem": ["trouble", "issue", "snag"],
    "promise": ["swear", "vow"],
    "protect": ["guard", "shield"],
    "pull": ["drag", "tug", "haul"],
    "put": ["set", "lay"],
    "safe": ["secure", "sound"],
    "sharp": ["keen"],
    "sleep": ["doze", "rest", "snooze", "nap"],
    "soft": ["silky", "downy"],
    "space": ["cosmos", "void"],
    "speak": ["talk", "say"],
    "stop": ["halt", "cease", "quit"],
    "stupid": ["dim", "dense", "dumb"],
    "travel": ["roam", "wander", "trek", "journey"],
    "traveler": ["wanderer", "stranger"],
    "traveller": ["wanderer", "stranger"],
    "upon": ["on"],
    "very": ["really", "so", "truly"],
    "victory": ["win", "triumph"],
    "view": ["sight", "scene"],
    "village": ["hamlet", "town"],
    "visit": ["call on", "see"],
    "voice": ["tone", "sound"],
    "weapon": ["arm"],
}

WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def difficulty(word):
    """How hard a word is for a cat to say: the cost of its p, b, f, v, ph and th sounds."""
    w, score = word.lower(), 0.0
    for sound, cost in HARD:
        score += w.count(sound) * cost
        w = w.replace(sound, " ")
    return score


def easiest(word):
    """The easiest alternative for word (lowercase), or None when nothing listed is easier."""
    options = SYNONYMS.get(word)
    suffix = ""
    if options is None and word.endswith("s") and word[:-1] in SYNONYMS:
        options, suffix = [o for o in SYNONYMS[word[:-1]] if " " not in o], "s"  # "friends" -> "mates"
    if not options:
        return None
    best = min(options, key=lambda o: (difficulty(o), len(o)))
    return best + suffix if difficulty(best) < difficulty(word) else None


def _match_case(original, new):
    if len(original) > 1 and original.isupper():
        return new.upper()
    if original[0].isupper():
        return new[:1].upper() + new[1:]
    return new


def cat_words(text):
    """Return text with hard-to-say words swapped for easier synonyms."""
    def swap(m):
        new = easiest(m.group(0).lower())
        return _match_case(m.group(0), new) if new else m.group(0)

    return WORD.sub(swap, text)


if __name__ == "__main__":
    import sys

    print(cat_words(" ".join(sys.argv[1:])))
