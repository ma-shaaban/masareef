export default function CategoryChips({ categories, value, onChange }) {
  return (
    <div className="chips" role="listbox" aria-label="Category">
      {categories.map((c) => (
        <button
          key={c.id}
          type="button"
          className={value === c.id ? 'active' : ''}
          aria-selected={value === c.id}
          onClick={() => onChange(value === c.id ? null : c.id)}
        >
          <span>{c.emoji}</span>
          {c.name}
        </button>
      ))}
    </div>
  )
}
