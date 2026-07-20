import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import CategoryChips from '../components/CategoryChips.jsx'
import { todayISO } from '../format.js'
import { useSpace } from '../spaces.jsx'

const PM_KEY = 'masareef.pm'
const PAYMENT_METHODS = [
  ['cash', '💵 Cash'],
  ['card', '💳 Card'],
  ['wallet', '📱 Wallet'],
  ['bank', '🏦 Bank'],
  ['other', '➰ Other'],
]

function yesterdayISO() {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`
}

export default function Add() {
  const { user } = useAuth()
  const { space } = useSpace()
  const [categories, setCategories] = useState([])
  const [members, setMembers] = useState([])
  const [amount, setAmount] = useState('')
  const [type, setType] = useState('expense')
  const [categoryId, setCategoryId] = useState(null)
  const [date, setDate] = useState(todayISO())
  const [pm, setPm] = useState(() => localStorage.getItem(PM_KEY) || 'cash')
  const [paidBy, setPaidBy] = useState(user.id)
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [busy, setBusy] = useState(false)
  const amountRef = useRef(null)

  useEffect(() => {
    api(`/api/spaces/${space.id}/categories`).then(setCategories).catch(() => {})
    api(`/api/spaces/${space.id}/members`).then(setMembers).catch(() => {})
    setCategoryId(null)
    setPaidBy(user.id)
  }, [space.id, user.id])

  const parsed = Number.parseFloat(amount)
  const valid = Number.isFinite(parsed) && parsed > 0

  async function submit(e) {
    e.preventDefault()
    if (!valid || busy) return
    setError('')
    setBusy(true)
    try {
      await api(`/api/spaces/${space.id}/transactions`, {
        method: 'POST',
        body: {
          amount: Math.round(parsed * 100) / 100,
          type,
          occurred_on: date,
          category_id: categoryId,
          payment_method: pm,
          paid_by: paidBy,
          description: description.trim(),
        },
      })
      localStorage.setItem(PM_KEY, pm)
      setAmount('')
      setDescription('')
      setToast('Saved ✓')
      setTimeout(() => setToast(''), 1800)
      amountRef.current?.focus()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <div className="seg">
        <button
          type="button"
          className={type === 'expense' ? 'active' : ''}
          onClick={() => setType('expense')}
        >
          Expense
        </button>
        <button
          type="button"
          className={type === 'income' ? 'active income-active' : ''}
          onClick={() => setType('income')}
        >
          Income
        </button>
      </div>

      <div className="amount-row">
        <span className="currency">{space.currency}</span>
        <input
          ref={amountRef}
          value={amount}
          onChange={(e) => setAmount(e.target.value.replace(/[^0-9.]/g, ''))}
          inputMode="decimal"
          placeholder="0"
          aria-label="Amount"
          autoFocus
        />
      </div>

      <CategoryChips categories={categories} value={categoryId} onChange={setCategoryId} />

      <div className="seg" aria-label="Date">
        <button
          type="button"
          className={date === todayISO() ? 'active' : ''}
          onClick={() => setDate(todayISO())}
        >
          Today
        </button>
        <button
          type="button"
          className={date === yesterdayISO() ? 'active' : ''}
          onClick={() => setDate(yesterdayISO())}
        >
          Yesterday
        </button>
        <input
          type="date"
          value={date}
          max={todayISO()}
          onChange={(e) => e.target.value && setDate(e.target.value)}
          aria-label="Pick a date"
          style={{ flex: 1.4, border: '1px solid var(--border)', borderRadius: 10, padding: '0 8px', background: 'var(--card)' }}
        />
      </div>

      <div className="seg" aria-label="Payment method">
        {PAYMENT_METHODS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={pm === value ? 'active' : ''}
            onClick={() => setPm(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {members.length > 1 && (
        <div className="field">
          <label htmlFor="paid-by">Paid by</label>
          <select id="paid-by" value={paidBy} onChange={(e) => setPaidBy(e.target.value)}>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.user_id === user.id ? `${m.display_name} (me)` : m.display_name}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="field">
        <label htmlFor="description">Note (optional)</label>
        <input
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What was it for?"
          maxLength={500}
        />
      </div>

      {error && <p className="error">{error}</p>}
      <button className="btn block" disabled={!valid || busy}>
        Add {type}
      </button>
      {toast && <div className="toast">{toast}</div>}
    </form>
  )
}
