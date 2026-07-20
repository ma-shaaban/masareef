import { useState } from 'react'
import { api } from '../api.js'

export default function CategoryManager({ spaceId, categories, onChanged }) {
  const [name, setName] = useState('')
  const [emoji, setEmoji] = useState('')
  const [error, setError] = useState('')

  async function add(e) {
    e.preventDefault()
    setError('')
    try {
      await api(`/api/spaces/${spaceId}/categories`, {
        method: 'POST',
        body: { name: name.trim(), emoji: emoji.trim() },
      })
      setName('')
      setEmoji('')
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function toggleArchive(cat) {
    setError('')
    try {
      await api(`/api/categories/${cat.id}`, {
        method: 'PATCH',
        body: { is_archived: !cat.is_archived },
      })
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function rename(cat) {
    const next = window.prompt('Rename category', cat.name)
    if (!next || next.trim() === cat.name) return
    setError('')
    try {
      await api(`/api/categories/${cat.id}`, { method: 'PATCH', body: { name: next.trim() } })
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function remove(cat) {
    if (!window.confirm(`Delete "${cat.name}"?`)) return
    setError('')
    try {
      await api(`/api/categories/${cat.id}`, { method: 'DELETE' })
      onChanged()
    } catch (err) {
      if (err.status === 409) {
        setError('That category has records — archive it instead.')
      } else {
        setError(err.message)
      }
    }
  }

  return (
    <div className="card">
      <h3>Categories</h3>
      {categories.map((cat) => (
        <div className="cat-row" key={cat.id}>
          <span>{cat.emoji}</span>
          <span className={`name ${cat.is_archived ? 'archived' : ''}`}>{cat.name}</span>
          <button type="button" className="linklike" onClick={() => rename(cat)}>
            Rename
          </button>
          <button type="button" className="linklike" onClick={() => toggleArchive(cat)}>
            {cat.is_archived ? 'Restore' : 'Archive'}
          </button>
          {cat.is_archived && (
            <button
              type="button"
              className="linklike"
              style={{ color: 'var(--danger)' }}
              onClick={() => remove(cat)}
            >
              Delete
            </button>
          )}
        </div>
      ))}
      <form onSubmit={add} className="sheet-row" style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <input
          value={emoji}
          onChange={(e) => setEmoji(e.target.value)}
          placeholder="🙂"
          aria-label="Emoji"
          maxLength={4}
          style={{ width: 52, textAlign: 'center', border: '1px solid var(--border)', borderRadius: 10, background: 'var(--bg)' }}
        />
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New category"
          aria-label="Category name"
          style={{ flex: 1, padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 10, background: 'var(--bg)' }}
        />
        <button className="btn secondary" disabled={!name.trim()}>
          Add
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
