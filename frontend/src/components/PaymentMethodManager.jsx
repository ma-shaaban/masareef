import { useState } from 'react'
import { api } from '../api.js'

export default function PaymentMethodManager({ spaceId, paymentMethods, onChanged }) {
  const [name, setName] = useState('')
  const [icon, setIcon] = useState('')
  const [error, setError] = useState('')

  async function add(e) {
    e.preventDefault()
    setError('')
    try {
      await api(`/api/spaces/${spaceId}/payment-methods`, {
        method: 'POST',
        body: { name: name.trim(), icon: icon.trim() },
      })
      setName('')
      setIcon('')
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function toggleArchive(pm) {
    setError('')
    try {
      await api(`/api/payment-methods/${pm.id}`, {
        method: 'PATCH',
        body: { is_archived: !pm.is_archived },
      })
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function rename(pm) {
    const next = window.prompt('Rename payment method', pm.name)
    if (!next || next.trim() === pm.name) return
    setError('')
    try {
      await api(`/api/payment-methods/${pm.id}`, { method: 'PATCH', body: { name: next.trim() } })
      onChanged()
    } catch (err) {
      setError(err.message)
    }
  }

  async function remove(pm) {
    if (!window.confirm(`Delete "${pm.name}"?`)) return
    setError('')
    try {
      await api(`/api/payment-methods/${pm.id}`, { method: 'DELETE' })
      onChanged()
    } catch (err) {
      if (err.status === 409) {
        setError('That payment method has records — archive it instead.')
      } else {
        setError(err.message)
      }
    }
  }

  return (
    <div className="card">
      <h3>Payment methods</h3>
      {paymentMethods.map((pm) => (
        <div className="cat-row" key={pm.id}>
          <span>{pm.icon}</span>
          <span className={`name ${pm.is_archived ? 'archived' : ''}`} dir="auto">
            {pm.name}
          </span>
          <button type="button" className="linklike" onClick={() => rename(pm)}>
            Rename
          </button>
          <button type="button" className="linklike" onClick={() => toggleArchive(pm)}>
            {pm.is_archived ? 'Restore' : 'Archive'}
          </button>
          {pm.is_archived && (
            <button
              type="button"
              className="linklike"
              style={{ color: 'var(--danger)' }}
              onClick={() => remove(pm)}
            >
              Delete
            </button>
          )}
        </div>
      ))}
      <form onSubmit={add} style={{ display: 'flex', gap: 8, marginTop: 10 }}>
        <input
          value={icon}
          onChange={(e) => setIcon(e.target.value)}
          placeholder="💳"
          aria-label="Icon"
          maxLength={4}
          style={{ width: 52, textAlign: 'center', border: '1px solid var(--border)', borderRadius: 10, background: 'var(--bg)' }}
        />
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="New payment method (e.g. Credit QNB)"
          aria-label="Payment method name"
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
