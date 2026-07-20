import { useState } from 'react'
import { api } from '../api.js'
import { todayISO } from '../format.js'

const PAYMENT_METHODS = [
  ['cash', 'Cash'],
  ['card', 'Card'],
  ['wallet', 'Wallet'],
  ['bank', 'Bank'],
  ['other', 'Other'],
]

export default function TxEditor({ tx, categories, members, onSaved, onDeleted, onClose }) {
  const [amount, setAmount] = useState(String(tx.amount))
  const [type, setType] = useState(tx.type)
  const [categoryId, setCategoryId] = useState(tx.category?.id || '')
  const [date, setDate] = useState(tx.occurred_on)
  const [pm, setPm] = useState(tx.payment_method)
  const [paidBy, setPaidBy] = useState(tx.paid_by || '')
  const [description, setDescription] = useState(tx.description)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const parsed = Number.parseFloat(amount)
  const valid = Number.isFinite(parsed) && parsed > 0

  async function save(e) {
    e.preventDefault()
    if (!valid || busy) return
    setError('')
    setBusy(true)
    try {
      const updated = await api(`/api/transactions/${tx.id}`, {
        method: 'PATCH',
        body: {
          amount: Math.round(parsed * 100) / 100,
          type,
          occurred_on: date,
          category_id: categoryId || null,
          payment_method: pm,
          paid_by: paidBy || null,
          description: description.trim(),
        },
      })
      onSaved(updated)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  async function remove() {
    if (!window.confirm('Delete this record?')) return
    setBusy(true)
    try {
      await api(`/api/transactions/${tx.id}`, { method: 'DELETE' })
      onDeleted(tx)
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <h2>Edit record</h2>
        <form onSubmit={save}>
          <div className="row">
            <div className="field">
              <label htmlFor="edit-amount">Amount</label>
              <input
                id="edit-amount"
                value={amount}
                inputMode="decimal"
                onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))}
              />
            </div>
            <div className="field">
              <label htmlFor="edit-type">Type</label>
              <select id="edit-type" value={type} onChange={(e) => setType(e.target.value)}>
                <option value="expense">Expense</option>
                <option value="income">Income</option>
              </select>
            </div>
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="edit-category">Category</label>
              <select
                id="edit-category"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
              >
                <option value="">No category</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.emoji} {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="edit-date">Date</label>
              <input
                id="edit-date"
                type="date"
                value={date}
                max={todayISO()}
                onChange={(e) => e.target.value && setDate(e.target.value)}
              />
            </div>
          </div>
          <div className="row">
            <div className="field">
              <label htmlFor="edit-pm">Payment</label>
              <select id="edit-pm" value={pm} onChange={(e) => setPm(e.target.value)}>
                {PAYMENT_METHODS.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label htmlFor="edit-paidby">Paid by</label>
              <select id="edit-paidby" value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
                {members.map((m) => (
                  <option key={m.user_id} value={m.user_id}>
                    {m.display_name}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="field">
            <label htmlFor="edit-note">Note</label>
            <input
              id="edit-note"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
            />
          </div>
          {error && <p className="error">{error}</p>}
          <div className="actions">
            <button type="button" className="btn danger" onClick={remove} disabled={busy}>
              Delete
            </button>
            <button className="btn" disabled={!valid || busy}>
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
