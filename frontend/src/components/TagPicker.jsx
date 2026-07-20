import { useState } from 'react'

/* Multi-select chips over the space's existing tags plus free entry for new
   ones. `value` is an array of tag names (strings). */
export default function TagPicker({ suggestions, value, onChange }) {
  const [draft, setDraft] = useState('')
  const selected = new Set(value.map((v) => v.toLowerCase()))
  const options = [
    ...suggestions.filter((s) => !selected.has(s.name.toLowerCase())).map((s) => s.name),
  ]

  function toggle(name) {
    if (selected.has(name.toLowerCase())) {
      onChange(value.filter((v) => v.toLowerCase() !== name.toLowerCase()))
    } else {
      onChange([...value, name])
    }
  }

  function addDraft() {
    const name = draft.trim()
    if (name && !selected.has(name.toLowerCase())) {
      onChange([...value, name])
    }
    setDraft('')
  }

  return (
    <div>
      <div className="chips">
        {value.map((name) => (
          <button key={name} type="button" className="active" dir="auto" onClick={() => toggle(name)}>
            {name} ✕
          </button>
        ))}
        {options.map((name) => (
          <button key={name} type="button" dir="auto" onClick={() => toggle(name)}>
            {name}
          </button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          value={draft}
          dir="auto"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              addDraft()
            }
          }}
          placeholder="New tag"
          aria-label="New tag"
          style={{ flex: 1, padding: '8px 10px', border: '1px solid var(--border)', borderRadius: 10, background: 'var(--bg)' }}
        />
        <button type="button" className="btn secondary" onClick={addDraft} disabled={!draft.trim()}>
          Add tag
        </button>
      </div>
    </div>
  )
}
