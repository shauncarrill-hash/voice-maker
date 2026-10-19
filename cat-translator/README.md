# Cat Voice Translator

A small desktop app: type or paste English and it respells it the way a humanoid cat would say it, ready to paste into [Chatterbox TTS](https://github.com/resemble-ai/chatterbox) (or the Voice Maker app in this repo). Output updates as you type; **Copy** puts it on the clipboard.

Built with Electron, React and Tailwind. The rules live in `src/translate.js` as plain functions, with tests in `src/translate.test.js`.

## Download (Windows)

Each push that touches `cat-translator/` builds Windows apps on GitHub Actions. Open the repo's **Actions** tab, pick the latest **Cat Translator (Windows build)** run, and download **cat-voice-translator-windows**. Inside is a portable `.exe` (no install, just run it) and a `Setup` installer. Windows SmartScreen will warn because the app isn't code-signed; click **More info → Run anyway**.

## Run from source

Needs Node.js 20 or newer.

```bash
npm install
npm start          # builds the UI and opens the app
npm run dev        # browser preview with hot reload at http://localhost:5173
npm test           # rule tests
npm run dist       # installer for your current OS, written to release/
```

## The rules

| What | Example |
| --- | --- |
| Lips don't close: p→t, b→d, m→n, w→y, v→z | "please" → "tlease", "water" → "yater" |
| Word-initial f becomes a hiss | "feed" → "sheed" |
| Vowel clusters are drawn out (toggle) | "you" → "youu" |
| Glottal attack before a word-initial vowel (toggle) | "is" → "’is" |
| Questions trail off | "?" → "...?" |
| Cat sounds after punctuation (choose a style) | "," → "... mrrr—", "." → ". prrr.", "!" → "! mrrrow!" |

Titles (Mr., Mrs., Ms., Dr.) are written out first, so "Mr. Brown" becomes "Nister Droyn". Each input line stays its own output line, so Voice Maker still makes one MP3 per line.

## Chatterbox notes

Chatterbox has no special syntax for cat sounds; it simply reads the text. So:

- **Spoken** (default) spells the sounds as something it can voice: "mrrr", "prrr", "mrrrow". Results vary by reference voice.
- **Tags** is the original script's style (`*mrr*`, `[purr]`, `*yowl*`). Chatterbox will likely ignore the symbols and read the words, so "[purr]" may come out as the word "purr".
- **None** keeps only the respelled speech and plain punctuation.
- The glottal mark (’) is probably ignored by Chatterbox; it's harmless if so.
- Ellipses and dashes do give pauses. In Voice Maker, an **Exaggeration** around 0.7 and **CFG / pace** around 0.3 make the delivery slower and more drawn out.

## Changes from the original HTML script

- Fixed a bug where each comma's "..." was then hit by the period rule and turned into "[purr] . [purr] . [purr] .". Punctuation is now handled in one pass.
- "Mr." used to become "nr" plus purrs; titles are now spelled out.
- Initial f now becomes "sh" instead of "s-h" (a hyphen tends to be read as separate letters).
- Vowel stretch repeats the vowel ("youu") instead of adding "~", which TTS doesn't voice.
- Decimals like 3.5 are left alone.
