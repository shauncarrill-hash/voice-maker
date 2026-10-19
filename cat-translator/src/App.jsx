import { useMemo, useState } from 'react'
import { DEFAULT_OPTIONS, translate } from './translate.js'

const SAMPLE = 'What are you doing with that water, mister?'

const SOUND_CHOICES = [
  ['spoken', 'Spoken (mrrr, prrr)'],
  ['tags', 'Tags (*mrr*, [purr])'],
  ['off', 'None'],
]

async function copyText(text) {
  if (window.catApp?.copy) return window.catApp.copy(text)
  return navigator.clipboard.writeText(text)
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm text-neutral-300">
      <input
        type="checkbox"
        className="h-4 w-4 accent-amber-400"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
      />
      {label}
    </label>
  )
}

export default function App() {
  const [input, setInput] = useState(SAMPLE)
  const [options, setOptions] = useState(DEFAULT_OPTIONS)
  const [copied, setCopied] = useState(false)
  const output = useMemo(() => translate(input, options), [input, options])
  const set = (key) => (value) => setOptions((o) => ({ ...o, [key]: value }))

  async function onCopy() {
    await copyText(output)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <main className="min-h-screen bg-neutral-950 px-4 py-8 text-neutral-100">
      <div className="mx-auto flex max-w-3xl flex-col gap-6">
        <header>
          <h1 className="text-2xl font-semibold text-amber-400">Cat Voice Translator</h1>
          <p className="mt-1 text-sm text-neutral-400">
            Type or paste English. The output is respelled the way a humanoid cat would say it, ready to paste
            into Chatterbox. Each line stays its own line.
          </p>
        </header>

        <section className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label htmlFor="input" className="text-sm font-medium">
              Your text
            </label>
            <button
              className="text-xs text-neutral-400 hover:text-neutral-200"
              onClick={() => setInput('')}
            >
              Clear
            </button>
          </div>
          <textarea
            id="input"
            rows={6}
            autoFocus
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="What are you doing with that water, mister?"
            className="w-full resize-y rounded-lg border border-neutral-700 bg-neutral-900 p-3 text-base outline-none focus:border-amber-400"
          />
        </section>

        <section className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
          <label className="flex items-center gap-2 text-sm text-neutral-300">
            Cat sounds
            <select
              value={options.sounds}
              onChange={(e) => set('sounds')(e.target.value)}
              className="rounded-md border border-neutral-700 bg-neutral-900 px-2 py-1 text-sm outline-none focus:border-amber-400"
            >
              {SOUND_CHOICES.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <Toggle label="Stretch vowels" checked={options.stretch} onChange={set('stretch')} />
          <Toggle label="Glottal attacks (’)" checked={options.glottal} onChange={set('glottal')} />
        </section>

        <section className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">Chatterbox-ready text</span>
            <button
              onClick={onCopy}
              disabled={!output.trim()}
              className="rounded-md bg-amber-400 px-4 py-2 text-sm font-semibold text-neutral-950 hover:bg-amber-300 disabled:opacity-40"
            >
              {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
          <pre className="min-h-32 whitespace-pre-wrap break-words rounded-lg border border-neutral-800 bg-black p-4 font-mono text-emerald-300 select-text">
            {output || ' '}
          </pre>
        </section>

        <footer className="text-xs leading-relaxed text-neutral-500">
          Chatterbox reads text literally, so cat sounds are spelled to be voiced ("mrrr") rather than acted out.
          Pick "None" if they come out as odd words. In Voice Maker, an Exaggeration around 0.7 and CFG / pace
          around 0.3 give a slower, more drawn-out delivery.
        </footer>
      </div>
    </main>
  )
}
