// 「貼上多行」: pasted text as steps, numbering stripped.
import { describe, expect, it } from 'vitest'

import { splitSteps, stepNumbers, stripNumbering } from './steps'

describe('splitSteps', () => {
  it('makes one step per non-blank line', () => {
    expect(splitSteps('切菜\n\n  下鍋  \n')).toEqual(['切菜', '下鍋'])
  })

  it.each([
    ['1. 切菜', '切菜'],
    ['1) 切菜', '切菜'],
    ['12、切菜', '切菜'],
    ['3：切菜', '切菜'],
    ['(2) 切菜', '切菜'],
    ['（2）切菜', '切菜'],
    ['① 切菜', '切菜'],
    ['⑩切菜', '切菜'],
    ['一、切菜', '切菜'],
    ['十二. 切菜', '切菜'],
    ['第一步：切菜', '切菜'],
    ['第3步 切菜', '切菜'],
    ['Step 4: chop', 'chop'],
    ['- 切菜', '切菜'],
    ['• 切菜', '切菜'],
  ])('strips the numbering from %j', (line, body) => {
    expect(stripNumbering(line)).toBe(body)
  })

  it('leaves a number that is part of the step alone', () => {
    expect(stripNumbering('180°C 烤 20 分鐘')).toBe('180°C 烤 20 分鐘')
    expect(stripNumbering('3 顆蛋打散')).toBe('3 顆蛋打散')
    expect(stripNumbering('一起拌勻')).toBe('一起拌勻')
  })

  it('handles Windows line endings', () => {
    expect(splitSteps('1. a\r\n2. b')).toEqual(['a', 'b'])
  })
})

describe('stepNumbers', () => {
  it('counts only ordinary steps; a step with no kind is ordinary', () => {
    expect(
      stepNumbers([{ kind: 'step' }, { kind: 'optional' }, {}, { kind: 'note' }, { kind: 'step' }]),
    ).toEqual([1, null, 2, null, 3])
  })

  it('answers nothing for no steps', () => {
    expect(stepNumbers([])).toEqual([])
  })
})
