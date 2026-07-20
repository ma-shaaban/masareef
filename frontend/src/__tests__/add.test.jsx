import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Add from '../pages/Add.jsx'

vi.mock('../auth.jsx', () => ({
  useAuth: () => ({ user: { id: 'u1', display_name: 'Ana' } }),
}))
vi.mock('../spaces.jsx', () => ({
  useSpace: () => ({ space: { id: 's1', name: 'Home', currency: 'EGP', role: 'owner' } }),
}))

const CATEGORIES = [
  { id: 'c1', name: 'Groceries', emoji: '🛒', color: '#4f9d69', sort_order: 0, is_archived: false },
  { id: 'c2', name: 'Dining', emoji: '🍽️', color: '#e07a5f', sort_order: 1, is_archived: false },
]
const MEMBERS = [{ user_id: 'u1', display_name: 'Ana', email: 'a@x.co', role: 'owner' }]
const PAYMENT_METHODS = [
  { id: 'p1', name: 'Cash', icon: '💵', sort_order: 0, is_archived: false },
  { id: 'p2', name: 'Credit QNB', icon: '💳', sort_order: 1, is_archived: false },
]

function stubFetch() {
  const calls = []
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, opts = {}) => {
      calls.push([url, opts])
      const u = String(url)
      const body =
        opts.method === 'POST'
          ? { id: 't1' }
          : u.includes('/categories')
            ? CATEGORIES
            : u.includes('/payment-methods')
              ? PAYMENT_METHODS
              : u.includes('/tags')
                ? []
                : MEMBERS
      return { ok: true, status: opts.method === 'POST' ? 201 : 200, json: async () => body }
    }),
  )
  return calls
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('Add', () => {
  it('renders category chips from the API', async () => {
    stubFetch()
    render(<Add />)
    expect(await screen.findByText('Groceries')).toBeTruthy()
    expect(screen.getByText('Dining')).toBeTruthy()
  })

  it('submit is disabled until a positive amount is entered', async () => {
    stubFetch()
    render(<Add />)
    await screen.findByText('Groceries')
    const submit = screen.getByRole('button', { name: /add expense/i })
    expect(submit.disabled).toBe(true)
    fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '125.5' } })
    expect(submit.disabled).toBe(false)
  })

  it('posts the record and resets amount but keeps category', async () => {
    const calls = stubFetch()
    render(<Add />)
    await screen.findByText('Groceries')
    fireEvent.click(screen.getByText('Groceries'))
    fireEvent.change(screen.getByLabelText('Amount'), { target: { value: '99' } })
    fireEvent.change(screen.getByLabelText('Note (optional)'), { target: { value: 'veggies' } })
    fireEvent.click(screen.getByRole('button', { name: /add expense/i }))

    await waitFor(() => {
      expect(calls.some(([, o]) => o.method === 'POST')).toBe(true)
    })
    const [url, opts] = calls.find(([, o]) => o.method === 'POST')
    expect(String(url)).toBe('/api/spaces/s1/transactions')
    const body = JSON.parse(opts.body)
    expect(body.amount).toBe(99)
    expect(body.category_id).toBe('c1')
    expect(body.type).toBe('expense')
    expect(body.description).toBe('veggies')
    expect(body.paid_by).toBe('u1')
    expect(body.payment_method_id).toBe('p1') // space's first method by default
    expect(body.tags).toEqual([])

    await waitFor(() => {
      expect(screen.getByLabelText('Amount').value).toBe('')
    })
    // category chip stays selected for the next entry
    expect(screen.getByText('Groceries').closest('button').className).toContain('active')
  })
})
