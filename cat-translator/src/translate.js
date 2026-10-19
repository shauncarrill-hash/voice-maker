// Feline-humanoid phonetic rules for Chatterbox TTS.
// Pure functions only, so the same rules run in the app and in tests.

export const SOUND_STYLES = {
  spoken: { comma: '... mrrr—', period: '. prrr.', exclaim: '! mrrrow!' },
  tags: { comma: '... *mrr*—', period: ' [purr].', exclaim: '! *yowl*' },
  off: { comma: '...', period: '.', exclaim: '!' },
}

export const DEFAULT_OPTIONS = {
  sounds: 'spoken', // 'spoken' | 'tags' | 'off'
  stretch: true,
  glottal: true,
}

// Expanded first so their periods don't trigger purrs.
const TITLES = [
  [/\bMrs\.?(?=\s|$)/g, 'Missus'],
  [/\bmrs\.?(?=\s|$)/gi, 'missus'],
  [/\bMr\.?(?=\s|$)/g, 'Mister'],
  [/\bmr\.?(?=\s|$)/gi, 'mister'],
  [/\bMs\.(?=\s|$)/g, 'Miz'],
  [/\bDr\.(?=\s|$)/g, 'Doctor'],
]

// Lips don't close: bilabials and labiodentals move forward in the mouth.
const LETTER_SHIFTS = { p: 't', b: 'd', m: 'n', w: 'y', v: 'z' }

function shiftLetters(text) {
  return text
    .replace(/[pbmwv]/gi, (c) => {
      const out = LETTER_SHIFTS[c.toLowerCase()]
      return c === c.toUpperCase() ? out.toUpperCase() : out
    })
    .replace(/\bf/g, 'sh')
    .replace(/\bF/g, 'Sh')
}

// Vowel clusters get drawn out by repeating their last vowel ("you" -> "youu").
function stretchVowels(text) {
  return text.replace(/[aeiou]{2,}/gi, (run) => run + run.slice(-1).toLowerCase())
}

// Glottal attack before word-initial vowels.
function addGlottal(text) {
  return text.replace(/\b(?<!['’])([aeiou])/gi, '’$1')
}

// One pass over punctuation so inserted markers are never re-processed.
function punctuate(text, sounds) {
  const s = SOUND_STYLES[sounds] ?? SOUND_STYLES.off
  return text.replace(/\.{3}|…|[,!?]|\.(?!\d)/g, (p) => {
    if (p === ',') return s.comma
    if (p === '.') return s.period
    if (p === '!') return s.exclaim
    if (p === '?') return '...?'
    return p // existing ellipsis stays a plain pause
  })
}

export function translateLine(line, options = DEFAULT_OPTIONS) {
  const opts = { ...DEFAULT_OPTIONS, ...options }
  let text = line
  for (const [re, word] of TITLES) text = text.replace(re, word)
  text = shiftLetters(text)
  if (opts.stretch) text = stretchVowels(text)
  if (opts.glottal) text = addGlottal(text)
  text = punctuate(text, opts.sounds)
  return text.replace(/[ \t]{2,}/g, ' ')
}

// Each input line stays its own line, so Voice Maker makes one MP3 per line.
export function translate(text, options = DEFAULT_OPTIONS) {
  return text
    .split(/\r?\n/)
    .map((line) => translateLine(line, options))
    .join('\n')
}
