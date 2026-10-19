import { test } from 'node:test'
import assert from 'node:assert/strict'
import { translate, translateLine } from './translate.js'

test('example phrase', () => {
  assert.equal(
    translateLine('What are you doing with that water, mister?'),
    'Yhat ’are youu doiing yith that yater... mrrr— nister...?',
  )
})

test('commas no longer turn into purr chains', () => {
  const out = translateLine('Hi, there.', { sounds: 'tags', stretch: false, glottal: false })
  assert.equal(out, 'Hi... *mrr*— there [purr].')
})

test('titles are expanded, not purred', () => {
  assert.equal(translateLine('Mr. Brown', { glottal: false, stretch: false }), 'Nister Droyn')
})

test('sounds off keeps plain punctuation', () => {
  assert.equal(translateLine('Wow! Feed me.', { sounds: 'off', stretch: false }), 'Yoy! Sheed ne.')
})

test('lines are kept separate and decimals untouched', () => {
  assert.equal(translate('pi is 3.5\nbye', { sounds: 'off', stretch: false, glottal: false }), 'ti is 3.5\ndye')
})
