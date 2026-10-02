// Guard: every <img> lazy-loads. media's guard, carried over. A library of
// cover images on a phone over the tunnel must not download every picture on
// the page at once; lazy loading is what keeps the first screen fast.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'

import { expect, it } from 'vitest'

// vitest runs from frontend/; import.meta.url is not a file: URL under jsdom.
const SRC = join(process.cwd(), 'src')
// An <img ...> or <img ... /> tag, across lines, up to its closing bracket.
const IMG_TAG = /<img\b[^>]*?\/?>/gs

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) yield* walk(p)
    else if (/\.jsx?$/.test(name) && !/\.test\.jsx?$/.test(name)) yield p
  }
}

function eagerLines(text) {
  const found = []
  for (const match of text.matchAll(IMG_TAG)) {
    if (!/\bloading="lazy"/.test(match[0])) {
      found.push(text.slice(0, match.index).split('\n').length)
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
