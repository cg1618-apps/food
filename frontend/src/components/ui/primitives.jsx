// Frontend: the notebook's design primitives.
//
// Hand-rolled rather than a component library, as media's are. Every page
// composes these instead of inventing its own button, input or badge markup,
// so the look stays one product and a change here changes it everywhere.
//
// Two rules hold for every component in this file:
//   - every colour is a semantic token (index.css, theme-tokens.test.js);
//   - `className` EXTENDS the base classes, it never replaces them. A layout
//     class like `sm:col-span-2` passed to an Input must not cost it its
//     border - the defect the first version of this file had.
import { useId, useRef } from 'react'
import { Link } from 'react-router-dom'

import { cx } from '../../lib/cx'

const FOCUS_RING =
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand focus-visible:ring-offset-1 focus-visible:ring-offset-canvas'

// Four kinds, media's set. `primary` is the one action a screen is for;
// `outline` everything else; `danger` destroys; `ghost` sits inside a row.
const BUTTON_KINDS = {
  primary: 'border border-brand bg-brand text-on-brand hover:border-brand-hover hover:bg-brand-hover',
  outline: 'border border-border-strong bg-surface text-text hover:border-text',
  danger: 'border border-danger bg-surface text-danger hover:bg-danger hover:text-on-brand',
  ghost: 'border border-transparent text-text-muted hover:bg-surface-2 hover:text-text',
}

const BUTTON_SIZES = {
  sm: 'px-2.5 py-1 text-xs',
  md: 'px-3.5 py-1.5 text-sm',
}

export function Button({ kind = 'outline', size = 'md', type = 'button', className, ...rest }) {
  return (
    <button
      type={type}
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        FOCUS_RING,
        BUTTON_SIZES[size] || BUTTON_SIZES.md,
        BUTTON_KINDS[kind] || BUTTON_KINDS.outline,
        className,
      )}
      {...rest}
    />
  )
}

// A link that looks like a Button. "Add a recipe" navigates rather than
// submits, so it is an <a>: it opens in a new tab like any other link.
export function LinkButton({ kind = 'outline', size = 'md', className, ...rest }) {
  return (
    <Link
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors',
        FOCUS_RING,
        BUTTON_SIZES[size] || BUTTON_SIZES.md,
        BUTTON_KINDS[kind] || BUTTON_KINDS.outline,
        className,
      )}
      {...rest}
    />
  )
}

// A label over a control, with an optional hint under it. A <label> wraps the
// control so clicking the words focuses it without an id to keep in step.
export function Field({ label, hint, className, children }) {
  return (
    <label className={cx('block space-y-1', className)}>
      <span className="text-sm font-medium text-text-muted">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-text-faint">{hint}</span> : null}
    </label>
  )
}

const CONTROL =
  'w-full rounded-md border border-border-strong bg-surface px-2.5 py-1.5 text-sm text-text placeholder:text-text-faint disabled:opacity-60'

export function Input({ className, ...rest }) {
  return <input className={cx(CONTROL, FOCUS_RING, className)} {...rest} />
}

export function TextArea({ className, rows = 4, ...rest }) {
  return (
    <textarea rows={rows} className={cx(CONTROL, FOCUS_RING, 'leading-relaxed', className)} {...rest} />
  )
}

export function Select({ className, children, ...rest }) {
  return (
    <select className={cx(CONTROL, FOCUS_RING, 'pr-8', className)} {...rest}>
      {children}
    </select>
  )
}

// A bordered panel. Used sparingly: the notebook separates most things with
// Section's rule, and a card is for a block that has to read as one object.
export function Card({ className, ...rest }) {
  return <div className={cx('rounded-lg border border-border bg-surface p-4', className)} {...rest} />
}

// A small rounded tag. Colour does not encode a category: every chip is ink,
// except `brand` for the one the page points at (a selected filter), `warn`
// for work still owed, `ok` for done, `danger` for the destructive.
const CHIP_TONES = {
  neutral: 'border-border bg-surface-2 text-text-muted',
  brand: 'border-brand/40 bg-brand-soft text-brand',
  warn: 'border-warn/40 bg-warn-soft text-warn',
  ok: 'border-ok/40 bg-surface text-ok',
  danger: 'border-danger/40 bg-surface text-danger',
}

export function Chip({ tone = 'neutral', className, children, ...rest }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs leading-tight',
        CHIP_TONES[tone] || CHIP_TONES.neutral,
        className,
      )}
      {...rest}
    >
      {children}
    </span>
  )
}

// The three badges a cover or a row can carry, named by what they mean so a
// page never re-decides their words or their tone:
//   bookmark - 書籤: a recipe saved but not written up yet;
//   stub     - 待補: an ingredient that exists only as a name;
//   rating   - the variety's grade, S to D, set in the serif like a stamp.
// A rating badge with no value renders nothing: there is no "unrated" mark.
export function Badge({ kind, value, className }) {
  if (kind === 'bookmark') {
    return (
      <Chip tone="neutral" className={className} title="只存了連結，還沒寫成食譜">
        書籤
      </Chip>
    )
  }
  if (kind === 'stub') {
    return (
      <Chip tone="warn" className={className} title="只有名字，細節待補">
        待補
      </Chip>
    )
  }
  if (kind === 'rating') {
    if (!value) return null
    return (
      <span
        className={cx(
          'inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-sm border border-brand font-display text-sm font-bold leading-none text-brand',
          className,
        )}
        title={`評等 ${value}`}
        aria-label={`評等 ${value}`}
      >
        {value}
      </span>
    )
  }
  return null
}

// A titled block in a single reading column: a serif heading on a ruled line,
// the way a notebook page is divided. `actions` sits at the right end of the
// rule. The heading level is a prop because a section under a page's h1 is an
// h2, and one inside a dialog may be an h3.
export function Section({ title, actions, as: Heading = 'h2', className, children, ...rest }) {
  return (
    <section className={cx('space-y-3', className)} {...rest}>
      {title || actions ? (
        <div className="flex items-baseline gap-3">
          {title ? (
            <Heading className="shrink-0 text-lg font-bold text-text">{title}</Heading>
          ) : null}
          <span aria-hidden="true" className="flex-1 translate-y-[-0.2em] border-t border-border" />
          {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
        </div>
      ) : null}
      {children}
    </section>
  )
}

// A two-or-more-way switch - the library's 封面 / 清單. Buttons with
// aria-pressed rather than radios: each is one click, and the pressed one is
// what a screen reader announces.
export function Toggle({ label, options, value, onChange, className }) {
  return (
    <div
      role="group"
      aria-label={label}
      className={cx('inline-flex rounded-md border border-border-strong bg-surface p-0.5', className)}
    >
      {options.map((option) => {
        const pressed = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={pressed}
            onClick={() => {
              if (!pressed) onChange(option.value)
            }}
            className={cx(
              'rounded-sm px-2.5 py-1 text-xs font-medium transition-colors',
              FOCUS_RING,
              pressed ? 'bg-brand-soft text-brand' : 'text-text-muted hover:text-text',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}

// A row of tabs over one panel - 設定's vocabularies. The WAI-ARIA tabs
// pattern: a tablist of tabs, each naming the panel it controls; only the
// selected tab is in the Tab order, and the arrow keys, Home and End move
// between tabs, selecting as they go. `children` is the selected tab's panel
// and nothing else, so a tab's content is mounted only while it is chosen.
//
// Drawn as media's AdminTabBar is - labels underlined in the brand hue on a
// rule, not pills - and the row wraps rather than scrolling sideways, so on a
// phone no tab is hidden off-screen.
//
//   label     what the tablist is called, for a screen reader
//   tabs      [{ id, label }], in order
//   selected  the id of the selected tab
//   onSelect  (id) => choose a tab
const TAB_KEYS = {
  ArrowRight: (index, count) => (index + 1) % count,
  ArrowLeft: (index, count) => (index - 1 + count) % count,
  Home: () => 0,
  End: (_index, count) => count - 1,
}

export function Tabs({ label, tabs, selected, onSelect, className, children }) {
  const prefix = useId()
  const refs = useRef({})
  const tabId = (id) => `${prefix}-tab-${id}`
  const panelId = (id) => `${prefix}-panel-${id}`

  function onKeyDown(event, index) {
    const move = TAB_KEYS[event.key]
    if (!move) return
    event.preventDefault()
    const next = tabs[move(index, tabs.length)]
    onSelect(next.id)
    refs.current[next.id]?.focus()
  }

  return (
    <div className={cx('space-y-6', className)}>
      <div role="tablist" aria-label={label} className="flex flex-wrap gap-x-1 border-b border-border">
        {tabs.map((tab, index) => {
          const isSelected = tab.id === selected
          return (
            <button
              key={tab.id}
              ref={(node) => {
                refs.current[tab.id] = node
              }}
              type="button"
              role="tab"
              id={tabId(tab.id)}
              aria-selected={isSelected}
              aria-controls={panelId(tab.id)}
              tabIndex={isSelected ? 0 : -1}
              onClick={() => {
                if (!isSelected) onSelect(tab.id)
              }}
              onKeyDown={(event) => onKeyDown(event, index)}
              className={cx(
                '-mb-px whitespace-nowrap rounded-t-sm border-b-2 px-3 py-2 text-sm font-medium transition-colors',
                FOCUS_RING,
                isSelected
                  ? 'border-brand text-text'
                  : 'border-transparent text-text-muted hover:text-text',
              )}
            >
              {tab.label}
            </button>
          )
        })}
      </div>
      <div role="tabpanel" id={panelId(selected)} aria-labelledby={tabId(selected)}>
        {children}
      </div>
    </div>
  )
}
