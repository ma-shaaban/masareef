// Money and date helpers. All dates in the app are plain local YYYY-MM-DD
// strings (the backend stores DATE, no timezones involved).

export function fmtMoney(n, currency = 'EGP') {
  try {
    return new Intl.NumberFormat('en', {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 2,
    }).format(n)
  } catch {
    return `${currency} ${n}`
  }
}

function toISO(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(
    d.getDate(),
  ).padStart(2, '0')}`
}

export function todayISO() {
  return toISO(new Date())
}

export function fmtDay(iso) {
  const now = new Date()
  if (iso === toISO(now)) return 'Today'
  now.setDate(now.getDate() - 1)
  if (iso === toISO(now)) return 'Yesterday'
  const d = new Date(`${iso}T00:00:00`)
  const sameYear = d.getFullYear() === new Date().getFullYear()
  return d.toLocaleDateString('en', {
    day: 'numeric',
    month: 'short',
    weekday: 'short',
    ...(sameYear ? {} : { year: 'numeric' }),
  })
}

export function monthLabel(ym) {
  const d = new Date(`${ym}-01T00:00:00`)
  return d.toLocaleDateString('en', { month: 'long', year: 'numeric' })
}

export function thisMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

export function addMonths(ym, n) {
  const [y, m] = ym.split('-').map(Number)
  const total = y * 12 + (m - 1) + n
  const ny = Math.floor(total / 12)
  const nm = (total % 12) + 1
  return `${ny}-${String(nm).padStart(2, '0')}`
}

export function monthRange(ym) {
  const [y, m] = ym.split('-').map(Number)
  const lastDay = new Date(y, m, 0).getDate()
  return { from: `${ym}-01`, to: `${ym}-${String(lastDay).padStart(2, '0')}` }
}
