import { useState } from 'react'
import { api } from '../api.js'

const CURRENCIES = ['EGP', 'USD', 'EUR', 'SAR', 'AED', 'GBP']
const KINDS = [
  ['household', 'Household'],
  ['shop', 'Shop'],
  ['company', 'Company'],
  ['other', 'Other'],
]

export default function CreateSpace({ onCreated }) {
  const [name, setName] = useState('')
  const [kind, setKind] = useState('household')
  const [currency, setCurrency] = useState('EGP')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const created = await api('/api/spaces', {
        method: 'POST',
        body: { name: name.trim(), kind, currency },
      })
      await onCreated(created)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <div className="field">
        <label htmlFor="space-name">Name</label>
        <input
          id="space-name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Our home"
          required
        />
      </div>
      <div className="field">
        <label htmlFor="space-kind">Type</label>
        <select id="space-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
          {KINDS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="field">
        <label htmlFor="space-currency">Currency</label>
        <select
          id="space-currency"
          value={currency}
          onChange={(e) => setCurrency(e.target.value)}
        >
          {CURRENCIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="error">{error}</p>}
      <button className="btn block" disabled={busy || !name.trim()}>
        Create space
      </button>
    </form>
  )
}
