import { useMemo, useState } from 'react'

/* Collapsed = a Filter button (with active count). Open = a bottom sheet
   with a search box + a vertical, tri-state category list: tap a row to
   cycle neutral → include ✓ → exclude ✕ → neutral. Selections apply live
   via onChange; Done just closes the sheet. */
export default function CategoryFilterSheet({ categories, include, exclude, onChange }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const activeCount = include.length + exclude.length

  function cycle(id) {
    if (include.includes(id)) {
      onChange(
        include.filter((i) => i !== id),
        [...exclude, id],
      )
    } else if (exclude.includes(id)) {
      onChange(
        include,
        exclude.filter((i) => i !== id),
      )
    } else {
      onChange([...include, id], exclude)
    }
  }

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return q ? categories.filter((c) => c.name.toLowerCase().includes(q)) : categories
  }, [categories, query])

  return (
    <>
      <button type="button" className="filter-btn" onClick={() => setOpen(true)}>
        <span>🔎 Filter{activeCount > 0 ? ` · ${activeCount} active` : ''}</span>
        <span aria-hidden="true">▾</span>
      </button>

      {open && (
        <div className="sheet-backdrop" onClick={() => setOpen(false)}>
          <div className="sheet" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-head">
              <h2>Filter by category</h2>
              <button
                type="button"
                className="linklike"
                disabled={activeCount === 0}
                onClick={() => onChange([], [])}
              >
                Clear
              </button>
            </div>

            <input
              className="filter-search"
              dir="auto"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search categories…"
              aria-label="Search categories"
              autoFocus
            />

            <div className="filter-list">
              {shown.length === 0 && <p className="empty">No matches</p>}
              {shown.map((c) => {
                const state = include.includes(c.id) ? 'in' : exclude.includes(c.id) ? 'out' : ''
                return (
                  <button
                    key={c.id}
                    type="button"
                    className={`filter-row ${state}`}
                    aria-pressed={state !== ''}
                    dir="auto"
                    onClick={() => cycle(c.id)}
                  >
                    <span className="mark" aria-hidden="true">
                      {state === 'in' ? '✓' : state === 'out' ? '✕' : ''}
                    </span>
                    <span aria-hidden="true">{c.emoji}</span>
                    <span className="label">{c.name}</span>
                  </button>
                )
              })}
            </div>

            <button type="button" className="btn block" onClick={() => setOpen(false)}>
              Done{activeCount > 0 ? ` (${activeCount})` : ''}
            </button>
          </div>
        </div>
      )}
    </>
  )
}
