// Guard: every <img> lazy-loads. media's guard, carried over. A library of
// cover images on a phone over the tunnel must not download every picture on
// the page at once; lazy loading is what keeps the first screen fast.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

import { expect, it } from 'vitest'

// vitest runs from frontend/; import.meta.url is not a file: URL under jsdom.
const SRC = join(process.cwd(), 'src')

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) yield* walk(p)
    else if (/\.jsx?$/.test(name) && !/\.test\.jsx?$/.test(name)) yield p
  }
}

// Every <img ...> tag, up to the ">" that closes it - focus-images.test.js's
// scanner. A regex stopping at the first ">" ends the tag inside an attribute
// like onError={(e) => ...} and never reads a loading= written after it, so
// the scan skips {...} expressions, quoted strings and comments.
function* imgTags(text) {
  const opener = /<img\b/g
  let m
  while ((m = opener.exec(text))) {
    let depth = 0
    let quote = null
    let i = m.index + 4
    for (; i < text.length; i++) {
      const c = text[i]
      if (quote) {
        if (c === quote) quote = null
      } else if (c === '/' && text[i + 1] === '/') {
        // A comment between attributes may hold an apostrophe or a ">".
        i = text.indexOf('\n', i)
        if (i === -1) break
      } else if (c === '/' && text[i + 1] === '*') {
        i = text.indexOf('*/', i) + 1
        if (i === 0) break
      } else if (c === '"' || c === "'" || c === '`') {
        quote = c
      } else if (c === '{') {
        depth++
      } else if (c === '}') {
        depth--
      } else if (c === '>' && depth === 0) {
        break
      }
    }
    yield { index: m.index, tag: text.slice(m.index, i + 1) }
  }
}

function eagerLines(text) {
  const found = []
  for (const { index, tag } of imgTags(text)) {
    if (!/\bloading="lazy"/.test(tag)) {
      found.push(text.slice(0, index).split('\n').length)
    }
  }
  return found
}

const files = [...walk(SRC)]

it('finds source files to scan', () => {
  // Without this the scan below passes on a wrong SRC path.
  expect(files.length).toBeGreaterThan(10)
})

// The scanner itself, on fixtures: the real scan is green while no page draws
// an image, whether or not the scanner could catch anything.
it('flags an eager image and passes a lazy one', () => {
  expect(eagerLines('<p />\n<img src={u} alt="" />')).toEqual([2])
  expect(eagerLines('<img\n  loading="lazy"\n  src={u}\n/>')).toEqual([])
  // A ">" inside an attribute (an arrow function) does not end the tag, so
  // what follows it is still read: lazy after one passes, eager is flagged.
  expect(eagerLines('<img onError={(e) => e} loading="lazy" src={u} />')).toEqual([])
  expect(eagerLines('<img onError={(e) => e} src={u} />')).toEqual([1])
})

it('lazy-loads every image', () => {
  const offenders = []
  for (const file of files) {
    for (const line of eagerLines(readFileSync(file, 'utf8'))) {
      offenders.push(`${relative(SRC, file)}:${line}`)
    }
  }
  expect(offenders).toEqual([])
})
