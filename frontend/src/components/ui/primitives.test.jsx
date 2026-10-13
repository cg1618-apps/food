import { createRef, useState } from 'react'
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { TextArea } from './primitives'

// jsdom does no layout, so scrollHeight is always 0. Stand in for the browser:
// LINE px per line of text, a line wrapping every `perLine` characters, and
// never less than the `rows` the box was given - which is what a real
// textarea reports once its height is back to `auto`.
const LINE = 20
// Under box-sizing: border-box a height includes the border and scrollHeight
// does not, so the hook has to add it back.
const BORDER = 1
const fit = (lines) => `${lines * LINE + 2 * BORDER}px`
let perLine = 40

const linesOf = (text) =>
  text.split('\n').reduce((total, line) => total + Math.max(1, Math.ceil(line.length / perLine)), 0)

// A ResizeObserver jsdom does not have: records each observer so a test can
// report a new width to it, as a window resize or a phone rotation would.
let observers = []
class FakeResizeObserver {
  constructor(callback) {
    this.callback = callback
    this.targets = []
    observers.push(this)
  }
  observe(target) {
    this.targets.push(target)
  }
  disconnect() {
    this.targets = []
  }
}
const resizeTo = (width) =>
  act(() => {
    for (const observer of observers) {
      for (const target of observer.targets) observer.callback([{ target, contentRect: { width } }], observer)
    }
  })

let originalScrollHeight
let originalResizeObserver
beforeEach(() => {
  perLine = 40
  observers = []
  originalResizeObserver = globalThis.ResizeObserver
  globalThis.ResizeObserver = FakeResizeObserver
  originalScrollHeight = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'scrollHeight')
  Object.defineProperty(HTMLTextAreaElement.prototype, 'scrollHeight', {
    configurable: true,
    get() {
      return Math.max(Number(this.getAttribute('rows')) || 2, linesOf(this.value)) * LINE
    },
  })
})
afterEach(() => {
  cleanup()
  globalThis.ResizeObserver = originalResizeObserver
  if (originalScrollHeight) {
    Object.defineProperty(HTMLTextAreaElement.prototype, 'scrollHeight', originalScrollHeight)
  } else {
    delete HTMLTextAreaElement.prototype.scrollHeight
  }
})

function Harness({ initial = '', rows }) {
  const [value, setValue] = useState(initial)
  return (
    <>
      <TextArea
        aria-label="步驟"
        rows={rows}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        style={{ boxSizing: 'border-box', borderStyle: 'solid', borderWidth: `${BORDER}px` }}
      />
      <button type="button" onClick={() => setValue('a\nb\nc\nd\ne\nf')}>套用範本</button>
      <button type="button" onClick={() => setValue('')}>清除</button>
    </>
  )
}

const box = () => screen.getByLabelText('步驟')

describe('TextArea', () => {
  it('fits its height to the text it opens with', () => {
    render(<Harness rows={2} initial={'one\ntwo\nthree\nfour'} />)
    expect(box().style.height).toBe(fit(4))
  })

  it('grows as lines are typed and shrinks as they are deleted', () => {
    render(<Harness rows={2} initial="one" />)
    fireEvent.change(box(), { target: { value: 'one\ntwo\nthree\nfour\nfive' } })
    expect(box().style.height).toBe(fit(5))
    fireEvent.change(box(), { target: { value: 'one\ntwo\nthree' } })
    expect(box().style.height).toBe(fit(3))
  })

  it('never goes below its rows, so an empty step still opens two lines high', () => {
    render(<Harness rows={2} />)
    expect(box()).toHaveProperty('rows', 2)
    expect(box().style.height).toBe(fit(2))
    fireEvent.change(box(), { target: { value: 'one\ntwo\nthree' } })
    fireEvent.change(box(), { target: { value: 'x' } })
    expect(box().style.height).toBe(fit(2))
  })

  it('re-fits when the value changes from outside, as a template or a reset does', () => {
    render(<Harness rows={2} />)
    fireEvent.click(screen.getByText('套用範本'))
    expect(box().style.height).toBe(fit(6))
    fireEvent.click(screen.getByText('清除'))
    expect(box().style.height).toBe(fit(2))
  })

  it('re-fits when its width changes and the text wraps differently', () => {
    render(<Harness rows={2} initial={'x'.repeat(120)} />)
    expect(box().style.height).toBe(fit(3))
    perLine = 20
    resizeTo(200)
    expect(box().style.height).toBe(fit(6))
  })

  it('has no scrollbar of its own and no drag handle', () => {
    render(<Harness rows={2} />)
    expect(box().className).toContain('overflow-y-hidden')
    expect(box().className).toContain('resize-none')
  })

  it('still hands a forwarded ref the element, and keeps the base classes', () => {
    const ref = createRef()
    render(<TextArea ref={ref} aria-label="備註" className="mt-2" value="" onChange={() => {}} />)
    expect(ref.current).toBe(screen.getByLabelText('備註'))
    expect(ref.current.className).toContain('mt-2')
    expect(ref.current.className).toContain('border-border-strong')
  })

  it('accepts a callback ref too', () => {
    let node = null
    render(<TextArea ref={(el) => (node = el)} aria-label="備註" value="" onChange={() => {}} />)
    expect(node).toBe(screen.getByLabelText('備註'))
  })
})
