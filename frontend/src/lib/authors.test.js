import { describe, expect, it } from 'vitest'

import { authorBody, authorDraft, matchesAuthor } from './authors'

const AUTHOR = {
  id: 3,
  name_cn: '阿基師',
  name_en: null,
  notes: '台菜。\n影片比較詳細。',
  links: [
    { label: 'YouTube', url: 'https://youtube.com/@a' },
    { label: null, url: 'https://blog.example/a' },
  ],
}

describe('authorDraft', () => {
  it('starts from the stored remark and links, each link keyed, a missing label empty', () => {
    const draft = authorDraft(AUTHOR)
    expect(draft.notes).toBe('台菜。\n影片比較詳細。')
    expect(draft.links.map(({ label, url }) => ({ label, url }))).toEqual([
      { label: 'YouTube', url: 'https://youtube.com/@a' },
      { label: '', url: 'https://blog.example/a' },
    ])
    expect(new Set(draft.links.map((row) => row._key)).size).toBe(2)
  })

  it('starts empty for an author with neither', () => {
    expect(authorDraft({ id: 1, name_cn: '甲' })).toMatchObject({ notes: '', links: [] })
  })
})

describe('authorBody', () => {
  it('sends the names, the remark with its line breaks, and the links in order, without keys', () => {
    const draft = { name_cn: '阿基師', name_en: '', ...authorDraft(AUTHOR) }
    expect(authorBody(draft)).toEqual({
      name_cn: '阿基師',
      name_en: '',
      notes: '台菜。\n影片比較詳細。',
      links: [
        { url: 'https://youtube.com/@a', label: 'YouTube' },
        { url: 'https://blog.example/a', label: null },
      ],
    })
  })

  it('sends a blank remark as null and leaves an empty link row out', () => {
    const draft = {
      name_cn: '甲',
      name_en: '',
      notes: '  \n ',
      links: [
        { _key: 'a', url: '  ', label: '' },
        { _key: 'b', url: ' blog.example ', label: ' 部落格 ' },
      ],
    }
    expect(authorBody(draft)).toEqual({
      name_cn: '甲',
      name_en: '',
      notes: null,
      links: [{ url: 'blog.example', label: '部落格' }],
    })
  })

  it('still sends a row with only a label, so the server can say it needs a link', () => {
    const draft = { name_cn: '甲', name_en: '', notes: '', links: [{ _key: 'a', url: '', label: 'IG' }] }
    expect(authorBody(draft).links).toEqual([{ url: '', label: 'IG' }])
  })
})

describe('matchesAuthor', () => {
  const author = { id: 3, display_name: '阿基師', name_cn: '阿基師', name_en: 'Chef Ah-Chi' }

  it('matches either name, ignoring case and outer space', () => {
    expect(matchesAuthor(author, '基師')).toBe(true)
    expect(matchesAuthor(author, '  chef ')).toBe(true)
    expect(matchesAuthor(author, 'AH-CHI')).toBe(true)
  })

  it('refuses a term neither name holds, and takes everyone for no term', () => {
    expect(matchesAuthor(author, '詹姆士')).toBe(false)
    expect(matchesAuthor(author, '')).toBe(true)
    expect(matchesAuthor(author, undefined)).toBe(true)
  })
})
