import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { api } from '../api.js'
import { SPACE_STORAGE_KEY } from '../spaces.jsx'

// Self-contained on purpose: this page must work for a brand-new user who
// has no space yet, so it renders OUTSIDE SpaceProvider (see App.jsx) and
// must not depend on useSpace(). Accepting remembers the joined space in
// localStorage; SpaceProvider picks it up when we navigate home.
export default function Invite() {
  const { code } = useParams()
  const navigate = useNavigate()
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api(`/api/invites/${code}`)
      .then(setPreview)
      .catch((err) =>
        setError(err.status === 404 ? 'This invite link is invalid or was revoked.' : err.message),
      )
  }, [code])

  async function accept() {
    setBusy(true)
    setError('')
    try {
      const space = await api(`/api/invites/${code}/accept`, { method: 'POST' })
      localStorage.setItem(SPACE_STORAGE_KEY, space.id)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="authpage">
      <h1>Masareef</h1>
      {error && <p className="error">{error}</p>}
      {!error && !preview && <p className="hint">Checking invite…</p>}
      {preview && (
        <div className="card">
          <h3>Join “{preview.space_name}”?</h3>
          <p className="meta">
            {preview.member_count} member{preview.member_count === 1 ? '' : 's'} so far. You'll see
            and add expenses together.
          </p>
          <button className="btn block" onClick={accept} disabled={busy} style={{ marginTop: 10 }}>
            Join space
          </button>
        </div>
      )}
    </div>
  )
}
