// The detail page's gallery: the large picture's caption, and none drawn when empty.
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import Gallery from './Gallery'

const image = (image_id, caption) => ({
  image_id,
  url: `/images/${image_id}.jpg`,
  thumb_url: `/images/t${image_id}.jpg`,
  width: 4,
  height: 3,
  focus: null,
  caption,
})

describe('Gallery', () => {
  afterEach(cleanup)

  it("shows the large picture's caption with its line breaks, and follows the chosen thumbnail", () => {
    const { container } = render(<Gallery title="番茄炒蛋" images={[image(1, '成品\n切開'), image(2, '備料')]} />)
    const caption = container.querySelector('p')
    expect(caption.textContent).toBe('成品\n切開')
    expect(caption.className).toContain('whitespace-pre-line')
    fireEvent.click(screen.getByRole('button', { name: '第 2 張' }))
    expect(container.querySelector('p').textContent).toBe('備料')
  })

  it('draws no caption for a picture without one', () => {
    // The first picture has a caption, so the mirror proves the second's
    // absence is the empty case rather than a gallery that never shows one.
    const { container } = render(<Gallery title="番茄炒蛋" images={[image(1, '成品'), image(2, null)]} />)
    expect(container.querySelector('p')).not.toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '第 2 張' }))
    expect(container.querySelector('p')).toBeNull()
  })
})
