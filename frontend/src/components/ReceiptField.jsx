import { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { compressImage, receiptUrl, uploadReceipt } from '../receipt.js'

/* Attach/view/remove a receipt photo.
   - mode="deferred": no tx yet (Add screen). Holds the compressed Blob and
     hands it to the parent via onPendingChange; parent uploads after create.
   - mode="live": tx exists (editor). Uploads/deletes immediately. */
export default function ReceiptField({ mode, txId, hasReceipt = false, onPendingChange }) {
  const inputRef = useRef(null)
  const [saved, setSaved] = useState(hasReceipt) // live: exists on server
  const [pendingUrl, setPendingUrl] = useState(null) // deferred: local preview
  const [bust, setBust] = useState(1)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [viewing, setViewing] = useState(false)

  useEffect(
    () => () => {
      if (pendingUrl) URL.revokeObjectURL(pendingUrl)
    },
    [pendingUrl],
  )

  const thumb =
    mode === 'deferred' ? pendingUrl : saved ? receiptUrl(txId, bust) : null

  async function pick(e) {
    const file = e.target.files?.[0]
    e.target.value = '' // allow re-picking the same file
    if (!file) return
    setError('')
    setBusy(true)
    try {
      const blob = await compressImage(file)
      if (mode === 'deferred') {
        if (pendingUrl) URL.revokeObjectURL(pendingUrl)
        setPendingUrl(URL.createObjectURL(blob))
        onPendingChange?.(blob)
      } else {
        await uploadReceipt(txId, blob)
        setSaved(true)
        setBust((b) => b + 1)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setError('')
    if (mode === 'deferred') {
      if (pendingUrl) URL.revokeObjectURL(pendingUrl)
      setPendingUrl(null)
      onPendingChange?.(null)
      return
    }
    setBusy(true)
    try {
      await api(`/api/transactions/${txId}/receipt`, { method: 'DELETE' })
      setSaved(false)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="field">
      <label>Receipt</label>
      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={pick}
        style={{ display: 'none' }}
        aria-label="Receipt photo"
      />

      {thumb ? (
        <div className="receipt">
          <img
            src={thumb}
            alt="Receipt"
            className="receipt-thumb"
            onClick={() => setViewing(true)}
          />
          <div className="receipt-actions">
            <button type="button" className="linklike" onClick={() => inputRef.current?.click()} disabled={busy}>
              Replace
            </button>
            <button type="button" className="linklike" style={{ color: 'var(--danger)' }} onClick={remove} disabled={busy}>
              Remove
            </button>
          </div>
        </div>
      ) : (
        <>
          <button
            type="button"
            className="btn secondary"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
          >
            📷 {busy ? 'Adding…' : 'Add receipt'}
          </button>
          <p className="hint">On your phone this opens the camera.</p>
        </>
      )}

      {error && <p className="error">{error}</p>}

      {viewing && thumb && (
        <div className="sheet-backdrop" onClick={() => setViewing(false)}>
          <img src={thumb} alt="Receipt" className="receipt-full" onClick={(e) => e.stopPropagation()} />
        </div>
      )}
    </div>
  )
}
