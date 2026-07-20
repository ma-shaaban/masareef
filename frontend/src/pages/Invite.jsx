import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { api } from '../api.js'
import { useSpace } from '../spaces.jsx'

export default function Invite() {
  const { code } = useParams()
  const navigate = useNavigate()
  const { setSpaceId, refresh } = useSpace()
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
      await refresh()
      setSpaceId(space.id)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err.message)
      setBusy(false)
    }
  }

  return (
    <div className="card" style={{ marginTop: 20 }}>
      {error && <p className="error">{error}</p>}
      {!error && !preview && <p className="hint">Checking invite…</p>}
      {preview && (
        <>
          <h3>Join “{preview.space_name}”?</h3>
          <p className="meta">
            {preview.member_count} member{preview.member_count === 1 ? '' : 's'} so far. You'll see
            and add expenses together.
          </p>
          <button className="btn block" onClick={accept} disabled={busy} style={{ marginTop: 10 }}>
            Join space
          </button>
        </>
      )}
    </div>
  )
}
