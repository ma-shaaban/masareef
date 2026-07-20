import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import TxEditor from '../components/TxEditor.jsx'
import { addMonths, fmtDay, fmtMoney, monthLabel, monthRange, thisMonth } from '../format.js'
import { useSpace } from '../spaces.jsx'

const PAGE = 100

export default function History() {
  const { space } = useSpace()
  const [month, setMonth] = useState(thisMonth())
  const [filters, setFilters] = useState({ category_id: '', paid_by: '', type: '', q: '' })
  const [data, setData] = useState({ items: [], total: 0 })
  const [categories, setCategories] = useState([])
  const [members, setMembers] = useState([])
  const [editing, setEditing] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    api(`/api/spaces/${space.id}/categories?include_archived=1`)
      .then(setCategories)
      .catch(() => {})
    api(`/api/spaces/${space.id}/members`).then(setMembers).catch(() => {})
  }, [space.id])

  const load = useCallback(
    async (offset = 0) => {
      setLoading(true)
      setError('')
      const { from, to } = monthRange(month)
      const params = new URLSearchParams({ from, to, limit: PAGE, offset })
      for (const [k, v] of Object.entries(filters)) {
        if (v) params.set(k, v)
      }
      try {
        const page = await api(`/api/spaces/${space.id}/transactions?${params}`)
        setData((prev) =>
          offset === 0 ? page : { items: [...prev.items, ...page.items], total: page.total },
        )
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    },
    [space.id, month, filters],
  )

  useEffect(() => {
    load(0)
  }, [load])

  const groups = []
  for (const tx of data.items) {
    const last = groups[groups.length - 1]
    if (last && last.date === tx.occurred_on) {
      last.items.push(tx)
    } else {
      groups.push({ date: tx.occurred_on, items: [tx] })
    }
  }

  return (
    <div>
      <div className="month-pager">
        <button type="button" aria-label="Previous month" onClick={() => setMonth(addMonths(month, -1))}>
          ‹
        </button>
        <h2>{monthLabel(month)}</h2>
        <button
          type="button"
          aria-label="Next month"
          onClick={() => setMonth(addMonths(month, 1))}
          disabled={month >= thisMonth()}
        >
          ›
        </button>
      </div>

      <div className="seg">
        <select
          value={filters.category_id}
          onChange={(e) => setFilters({ ...filters, category_id: e.target.value })}
          style={{ flex: 1, padding: 9, borderRadius: 10, border: '1px solid var(--border)', background: 'var(--card)' }}
        >
          <option value="">All categories</option>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.emoji} {c.name}
            </option>
          ))}
        </select>
        {members.length > 1 && (
          <select
            value={filters.paid_by}
            onChange={(e) => setFilters({ ...filters, paid_by: e.target.value })}
            style={{ flex: 1, padding: 9, borderRadius: 10, border: '1px solid var(--border)', background: 'var(--card)' }}
          >
            <option value="">Everyone</option>
            {members.map((m) => (
              <option key={m.user_id} value={m.user_id}>
                {m.display_name}
              </option>
            ))}
          </select>
        )}
        <select
          value={filters.type}
          onChange={(e) => setFilters({ ...filters, type: e.target.value })}
          style={{ flex: 1, padding: 9, borderRadius: 10, border: '1px solid var(--border)', background: 'var(--card)' }}
        >
          <option value="">All</option>
          <option value="expense">Expenses</option>
          <option value="income">Income</option>
        </select>
      </div>

      {error && <p className="error">{error}</p>}
      {!loading && data.total === 0 && (
        <p className="empty">No records this month. Add your first from the ➕ tab.</p>
      )}

      {groups.map((g) => {
        const spent = g.items
          .filter((t) => t.type === 'expense')
          .reduce((sum, t) => sum + t.amount, 0)
        return (
          <div key={g.date}>
            <div className="day-head">
              <span>{fmtDay(g.date)}</span>
              {spent > 0 && <span>{fmtMoney(spent, space.currency)}</span>}
            </div>
            {g.items.map((tx) => (
              <div key={tx.id} className="tx" onClick={() => setEditing(tx)}>
                <span className="emoji">{tx.type === 'income' ? '💰' : tx.category?.emoji || '❔'}</span>
                <div className="body">
                  <div className="title">
                    {tx.description || tx.category?.name || (tx.type === 'income' ? 'Income' : 'Expense')}
                  </div>
                  <div className="sub">
                    {[tx.description ? tx.category?.name : null, tx.paid_by_name, tx.payment_method]
                      .filter(Boolean)
                      .join(' · ')}
                  </div>
                </div>
                <span className={`amount ${tx.type}`}>
                  {tx.type === 'income' ? '+' : '−'}
                  {fmtMoney(tx.amount, space.currency)}
                </span>
              </div>
            ))}
          </div>
        )
      })}

      {data.items.length < data.total && (
        <button className="btn secondary block" onClick={() => load(data.items.length)} disabled={loading}>
          Load more ({data.items.length}/{data.total})
        </button>
      )}

      {editing && (
        <TxEditor
          tx={editing}
          categories={categories.filter((c) => !c.is_archived || c.id === editing.category?.id)}
          members={members}
          onSaved={() => {
            setEditing(null)
            load(0)
          }}
          onDeleted={() => {
            setEditing(null)
            load(0)
          }}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  )
}
