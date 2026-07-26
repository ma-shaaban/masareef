import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

// The invite page must work for a brand-new user who has NO space yet, so it
// must NOT depend on SpaceProvider. Render it bare (no provider) here.
const navigate = vi.fn()
vi.mock('react-router', () => ({
  useParams: () => ({ code: 'abc' }),
  useNavigate: () => navigate,
}))
vi.mock('../api.js', () => ({ api: vi.fn() }))

import Invite from '../pages/Invite.jsx'
import { api } from '../api.js'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  localStorage.clear()
})

describe('Invite (no space required)', () => {
  it('previews, accepts, remembers the joined space, and navigates home', async () => {
    api.mockImplementation((path, opts) =>
      opts?.method === 'POST'
        ? Promise.resolve({ id: 'fam1', name: 'Family', role: 'member' })
        : Promise.resolve({ space_name: 'Family', member_count: 2 }),
    )

    render(<Invite />)
    await waitFor(() => expect(screen.getByText(/Family/)).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: /join space/i }))

    await waitFor(() =>
      expect(api).toHaveBeenCalledWith('/api/invites/abc/accept', { method: 'POST' }),
    )
    // remembers the joined space so SpaceProvider selects it on next mount
    expect(localStorage.getItem('masareef.space')).toBe('fam1')
    expect(navigate).toHaveBeenCalledWith('/', { replace: true })
  })

  it('shows a friendly error for an invalid/revoked invite', async () => {
    api.mockRejectedValue(Object.assign(new Error('nope'), { status: 404 }))
    render(<Invite />)
    await waitFor(() =>
      expect(screen.getByText(/invalid or was revoked/i)).toBeTruthy(),
    )
  })
})
