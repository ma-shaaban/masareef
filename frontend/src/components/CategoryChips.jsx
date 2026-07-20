/* Ordered multi-select: `value` is an array of category ids; the first is
   the record's MAIN category (drives the charts) and gets a star. */
export default function CategoryChips({ categories, value, onChange }) {
  function toggle(id) {
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id])
  }
  return (
    <div className="chips" role="listbox" aria-label="Categories" aria-multiselectable="true">
      {categories.map((c) => {
        const selected = value.includes(c.id)
        return (
          <button
            key={c.id}
            type="button"
            className={selected ? 'active' : ''}
            aria-selected={selected}
            dir="auto"
            onClick={() => toggle(c.id)}
          >
            <span>{c.emoji}</span>
            {c.name}
            {value[0] === c.id && value.length > 1 && <span title="Main category">★</span>}
          </button>
        )
      })}
    </div>
  )
}
