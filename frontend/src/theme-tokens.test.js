import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

// Hard-coded colours are how four apps stop looking like one product, and how
// dark mode rots one component at a time. Tokens are declared in index.css and
// nowhere else; this is what says so.
const BANNED = /\b(?:bg|text|border|ring|from|to)-(?:gray|zinc|slate|neutral|stone)-\d{2,3}\b/
const HEX = /(?:bg|text|border)-\[#[0-9a-fA-F]{3,8}\]/

function jsxFiles(dir, found = []) {
  for (const entry of readdirSync(dir)) {
    const path = join(dir, entry)
    if (statSync(path).isDirectory()) jsxFiles(path, found)
    else if (entry.endsWith('.jsx')) found.push(path)
  }
  return found
}

describe('colours come from semantic tokens', () => {
  const files = jsxFiles(dirname(fileURLToPath(import.meta.url)))

  it('finds components to check', () => {
    // Without this the loop below passes on an empty directory.
    expect(files.length).toBeGreaterThan(3)
  })

  it.each(files)('%s uses no numbered grey or raw hex', (file) => {
    const source = readFileSync(file, 'utf8')
    expect(source).not.toMatch(BANNED)
    expect(source).not.toMatch(HEX)
  })
})
