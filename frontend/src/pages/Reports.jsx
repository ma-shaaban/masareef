import { useEffect, useState } from 'react'
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api.js'
import { addMonths, fmtMoney, monthLabel, monthRange, thisMonth } from '../format.js'
import { useSpace } from '../spaces.jsx'

const FALLBACK_COLORS = ['#0e9f6e', '#3d8bd4', '#e07a5f', '#f2b134', '#8d6ba8', '#d64550', '#2a9d8f', '#e76f9b']
const PRESETS = [
  ['month', 'Monthly'],
  ['3m', 'Last 3 months'],
  ['year', 'This year'],
]

function rangeFor(preset, month) {
  if (preset === 'month') return monthRange(month)
  if (preset === '3m') {
    return { from: monthRange(addMonths(thisMonth(), -2)).from, to: monthRange(thisMonth()).to }
  }
  const year = new Date().getFullYear()
  return { from: `${year}-01-01`, to: `${year}-12-31` }
}

export default function Reports() {
  const { space } = useSpace()
  const [preset, setPreset] = useState('month')
  const [month, setMonth] = useState(thisMonth())
  const [summary, setSummary] = useState(null)
  const [byCategory, setByCategory] = useState([])
  const [byMember, setByMember] = useState([])
  const [monthly, setMonthly] = useState([])
  const [error, setError] = useState('')

  const { from, to } = rangeFor(preset, month)

  useEffect(() => {
    setError('')
    const params = new URLSearchParams({ from, to })
    Promise.all([
      preset === 'month'
        ? api(`/api/spaces/${space.id}/reports/summary?month=${month}`)
        : Promise.resolve(null),
      api(`/api/spaces/${space.id}/reports/by-category?${params}`),
      api(`/api/spaces/${space.id}/reports/by-member?${params}`),
      api(`/api/spaces/${space.id}/reports/monthly?months=12`),
    ])
      .then(([s, cats, mems, months]) => {
        setSummary(s)
        setByCategory(cats)
        setByMember(mems)
        setMonthly(months)
      })
      .catch((err) => setError(err.message))
  }, [space.id, preset, month, from, to])

  const money = (n) => fmtMoney(n, space.currency)
  const rangeTotal = byCategory.reduce((sum, c) => sum + c.total, 0)
  const donutData = byCategory.slice(0, 8)
  const donutRest = byCategory.slice(8).reduce((sum, c) => sum + c.total, 0)
  if (donutRest > 0) {
    donutData.push({ category_id: 'rest', name: 'Other', color: '#8a8f98', total: donutRest, pct: 0 })
  }
  const memberMax = Math.max(...byMember.map((m) => m.total), 1)

  const delta =
    summary && summary.prev_expense_total > 0
      ? ((summary.expense_total - summary.prev_expense_total) / summary.prev_expense_total) * 100
      : null

  return (
    <div>
      <div className="seg">
        {PRESETS.map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={preset === value ? 'active' : ''}
            onClick={() => setPreset(value)}
          >
            {label}
          </button>
        ))}
      </div>

      {preset === 'month' && (
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
      )}

      {error && <p className="error">{error}</p>}

      <div className="summary-cards">
        <div className="card">
          <div className="meta">Spent</div>
          <div className="big">{money(preset === 'month' && summary ? summary.expense_total : rangeTotal)}</div>
          {delta !== null && (
            <div className={`delta ${delta >= 0 ? 'up' : 'down'}`}>
              {delta >= 0 ? '▲' : '▼'} {Math.abs(delta).toFixed(0)}% vs {monthLabel(addMonths(month, -1))}
            </div>
          )}
        </div>
        {preset === 'month' && summary && summary.income_total > 0 && (
          <div className="card">
            <div className="meta">Income</div>
            <div className="big" style={{ color: 'var(--income)' }}>
              {money(summary.income_total)}
            </div>
          </div>
        )}
      </div>

      {byCategory.length === 0 ? (
        <p className="empty">Nothing recorded in this period yet.</p>
      ) : (
        <div className="card">
          <h3>By category</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={donutData}
                dataKey="total"
                nameKey="name"
                innerRadius={55}
                outerRadius={85}
                strokeWidth={0}
              >
                {donutData.map((c, i) => (
                  <Cell key={c.category_id ?? 'un'} fill={c.color || FALLBACK_COLORS[i % FALLBACK_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(v) => money(v)} />
            </PieChart>
          </ResponsiveContainer>
          <div className="legend">
            {byCategory.map((c, i) => (
              <div className="row" key={c.category_id ?? 'un'}>
                <span
                  className="dot"
                  style={{ background: c.color || FALLBACK_COLORS[i % FALLBACK_COLORS.length] }}
                />
                <span className="name">
                  {c.emoji} {c.name}
                </span>
                <span className="val">
                  {money(c.total)} · {c.pct}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {preset === 'month' && summary && summary.daily.length > 0 && (
        <div className="card">
          <h3>Daily spend</h3>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={summary.daily.map((d) => ({ ...d, day: Number(d.date.slice(8)) }))}>
              <XAxis dataKey="day" tickLine={false} axisLine={false} fontSize={11} />
              <Tooltip formatter={(v) => money(v)} labelFormatter={(d) => `Day ${d}`} />
              <Bar dataKey="total" fill="var(--accent)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {byMember.length > 1 && (
        <div className="card">
          <h3>Who paid</h3>
          <div className="legend">
            {byMember.map((m) => (
              <div className="row" key={m.user_id ?? 'un'}>
                <span className="name">{m.display_name}</span>
                <div
                  style={{
                    flex: 2,
                    height: 8,
                    background: 'var(--accent-soft)',
                    borderRadius: 4,
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      width: `${(m.total / memberMax) * 100}%`,
                      height: '100%',
                      background: 'var(--accent)',
                    }}
                  />
                </div>
                <span className="val">{money(m.total)}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {monthly.some((m) => m.total > 0) && (
        <div className="card">
          <h3>Last 12 months</h3>
          <ResponsiveContainer width="100%" height={140}>
            <BarChart data={monthly.map((m) => ({ ...m, label: monthLabel(m.month).slice(0, 3) }))}>
              <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={10} interval={1} />
              <YAxis hide />
              <Tooltip formatter={(v) => money(v)} />
              <Bar dataKey="total" fill="var(--accent)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
