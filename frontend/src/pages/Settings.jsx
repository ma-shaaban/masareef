import { useCallback, useEffect, useState } from 'react'
import { api } from '../api.js'
import { useAuth } from '../auth.jsx'
import CategoryManager from '../components/CategoryManager.jsx'
import PaymentMethodManager from '../components/PaymentMethodManager.jsx'
import CreateSpace from './CreateSpace.jsx'
import { useSpace } from '../spaces.jsx'

const CURRENCIES = ['EGP', 'USD', 'EUR', 'SAR', 'AED', 'GBP']

export default function Settings() {
  const { user, update, logout } = useAuth()
  const { space, spaces, setSpaceId, refresh } = useSpace()
  const isOwner = space.role === 'owner'
  const [displayName, setDisplayName] = useState(user.display_name)
  const [members, setMembers] = useState([])
  const [invites, setInvites] = useState([])
  const [categories, setCategories] = useState([])
  const [paymentMethods, setPaymentMethods] = useState([])
  const [showNewSpace, setShowNewSpace] = useState(false)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState('')

  const loadSpaceData = useCallback(() => {
    api(`/api/spaces/${space.id}/members`).then(setMembers).catch(() => {})
    api(`/api/spaces/${space.id}/invites`).then(setInvites).catch(() => {})
    api(`/api/spaces/${space.id}/payment-methods?include_archived=1`)
      .then(setPaymentMethods)
      .catch(() => {})
    api(`/api/spaces/${space.id}/categories?include_archived=1`)
      .then(setCategories)
      .catch(() => {})
  }, [space.id])

  useEffect(() => {
    loadSpaceData()
  }, [loadSpaceData])

  async function saveName() {
    if (displayName.trim() === user.display_name) return
    try {
      await update({ display_name: displayName.trim() })
    } catch (err) {
      setError(err.message)
    }
  }

  async function patchSpace(fields) {
    setError('')
    try {
      await api(`/api/spaces/${space.id}`, { method: 'PATCH', body: fields })
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function createInvite() {
    setError('')
    try {
      await api(`/api/spaces/${space.id}/invites`, { method: 'POST' })
      loadSpaceData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function revokeInvite(inv) {
    try {
      await api(`/api/spaces/${space.id}/invites/${inv.id}`, { method: 'DELETE' })
      loadSpaceData()
    } catch (err) {
      setError(err.message)
    }
  }

  async function copyInvite(inv) {
    const url = `${window.location.origin}/invite/${inv.code}`
    try {
      await navigator.clipboard.writeText(url)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      window.prompt('Copy this invite link', url)
    }
  }

  async function removeMember(m) {
    const leaving = m.user_id === user.id
    if (!window.confirm(leaving ? 'Leave this space?' : `Remove ${m.display_name}?`)) return
    setError('')
    try {
      await api(`/api/spaces/${space.id}/members/${m.user_id}`, { method: 'DELETE' })
      if (leaving) {
        await refresh()
      } else {
        loadSpaceData()
      }
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}

      <div className="section-title">Profile</div>
      <div className="card">
        <div className="field">
          <label htmlFor="display-name">Your name</label>
          <input
            id="display-name"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            onBlur={saveName}
          />
        </div>
        <div className="meta">{user.email}</div>
      </div>

      <div className="section-title">Space</div>
      <div className="card">
        {isOwner ? (
          <>
            <div className="field">
              <label htmlFor="space-name">Name</label>
              <input
                id="space-name"
                defaultValue={space.name}
                onBlur={(e) => {
                  const v = e.target.value.trim()
                  if (v && v !== space.name) patchSpace({ name: v })
                }}
              />
            </div>
            <div className="field">
              <label htmlFor="space-currency">Currency</label>
              <select
                id="space-currency"
                value={space.currency}
                onChange={(e) => patchSpace({ currency: e.target.value })}
              >
                {CURRENCIES.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
          </>
        ) : (
          <div className="meta">
            {space.name} · {space.currency}
          </div>
        )}
      </div>

      {spaces.length > 1 && (
        <div className="card">
          <h3>Switch space</h3>
          {spaces.map((s) => (
            <div className="cat-row" key={s.id}>
              <span className="name">{s.name}</span>
              {s.id === space.id ? (
                <span className="role">current</span>
              ) : (
                <button type="button" className="linklike" onClick={() => setSpaceId(s.id)}>
                  Switch
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      {showNewSpace ? (
        <div className="card">
          <h3>New space</h3>
          <CreateSpace
            onCreated={async (created) => {
              await refresh()
              setSpaceId(created.id)
              setShowNewSpace(false)
            }}
          />
        </div>
      ) : (
        <button type="button" className="linklike" onClick={() => setShowNewSpace(true)}>
          + New space
        </button>
      )}

      <div className="section-title">Members</div>
      {members.map((m) => (
        <div className="member" key={m.user_id}>
          <span className="name">
            {m.display_name}
            {m.user_id === user.id && ' (me)'}
          </span>
          <span className="role">{m.role}</span>
          {(m.user_id === user.id || isOwner) && (
            <button type="button" className="linklike" onClick={() => removeMember(m)}>
              {m.user_id === user.id ? 'Leave' : 'Remove'}
            </button>
          )}
        </div>
      ))}
      <div className="card">
        <h3>Invite someone</h3>
        {invites.map((inv) => (
          <div className="invite-box" key={inv.id}>
            {window.location.origin}/invite/{inv.code}
            <div style={{ marginTop: 6, display: 'flex', gap: 14 }}>
              <button type="button" className="linklike" onClick={() => copyInvite(inv)}>
                {copied ? 'Copied ✓' : 'Copy link'}
              </button>
              <button
                type="button"
                className="linklike"
                style={{ color: 'var(--danger)' }}
                onClick={() => revokeInvite(inv)}
              >
                Revoke
              </button>
            </div>
          </div>
        ))}
        {invites.length === 0 && (
          <button type="button" className="btn secondary" onClick={createInvite}>
            Create invite link
          </button>
        )}
      </div>

      <div className="section-title">Categories</div>
      <CategoryManager spaceId={space.id} categories={categories} onChanged={loadSpaceData} />

      <div className="section-title">Payment methods</div>
      <PaymentMethodManager
        spaceId={space.id}
        paymentMethods={paymentMethods}
        onChanged={loadSpaceData}
      />

      <div className="section-title">Account</div>
      <button type="button" className="btn danger block" onClick={logout}>
        Log out
      </button>
    </div>
  )
}
