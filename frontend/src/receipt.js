// Receipt image helpers: client-side compression (receipts are just numbers,
// so we downscale + re-encode JPEG to keep uploads tiny) and raw upload.

export async function compressImage(file, maxDim = 1600, quality = 0.72) {
  if (!file || !file.type?.startsWith('image/')) return file
  try {
    const bitmap = await createImageBitmap(file)
    const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height))
    const w = Math.max(1, Math.round(bitmap.width * scale))
    const h = Math.max(1, Math.round(bitmap.height * scale))
    const canvas = document.createElement('canvas')
    canvas.width = w
    canvas.height = h
    canvas.getContext('2d').drawImage(bitmap, 0, 0, w, h)
    const blob = await new Promise((res) => canvas.toBlob(res, 'image/jpeg', quality))
    bitmap.close?.()
    // Keep whichever is smaller — a small photo re-encoded can grow.
    return blob && blob.size < file.size ? blob : file
  } catch {
    // No canvas/bitmap support (or a decode error) — upload the original.
    return file
  }
}

export async function uploadReceipt(txId, blob) {
  const res = await fetch(`/api/transactions/${txId}/receipt`, {
    method: 'POST',
    headers: { 'content-type': blob.type || 'image/jpeg' },
    body: blob,
  })
  if (!res.ok) {
    let detail = 'Receipt upload failed'
    try {
      detail = (await res.json()).detail || detail
    } catch {
      // non-JSON error body
    }
    throw new Error(detail)
  }
  return res.json()
}

export function receiptUrl(txId, bust = 0) {
  return `/api/transactions/${txId}/receipt${bust ? `?b=${bust}` : ''}`
}
