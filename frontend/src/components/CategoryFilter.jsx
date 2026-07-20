/* Tri-state category filter chips: tap cycles neutral → ✓ include →
   ✕ exclude → neutral. `include`/`exclude` are arrays of category ids. */
export default function CategoryFilter({ categories, include, exclude, onChange }) {
  function cycle(id) {
    if (include.includes(id)) {
      onChange(include.filter((i) => i !== id), [...exclude, id])
    } else if (exclude.includes(id)) {
      onChange(include, exclude.filter((i) => i !== id))
    } else {
      onChange([...include, id], exclude)
    }
  }
  const active = include.length > 0 || exclude.length > 0
  return (
    <div className="chips scroll" aria-label="Filter by category">
      {active && (
        <button type="button" className="clear" onClick={() => onChange([], [])}>
          Clear
        </button>
      )}
      {categories.map((c) => {
        const state = include.includes(c.id) ? 'in' : exclude.includes(c.id) ? 'out' : ''
        return (
          <button
            key={c.id}
            type="button"
            className={state === 'in' ? 'active' : state === 'out' ? 'exclude' : ''}
            aria-pressed={state !== ''}
            title={
              state === ''
                ? `Show only ${c.name}`
                : state === 'in'
                  ? `Tap to hide ${c.name}`
                  : `Tap to reset ${c.name}`
            }
            dir="auto"
            onClick={() => cycle(c.id)}
          >
            {state === 'in' && <span>✓</span>}
            {state === 'out' && <span>✕</span>}
            <span>{c.emoji}</span>
            {c.name}
          </button>
        )
      })}
    </div>
  )
}
