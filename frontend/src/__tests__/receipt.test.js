import { afterEach, describe, expect, it, vi } from 'vitest'
import { compressImage, receiptUrl, uploadReceipt } from '../receipt.js'

afterEach(() => vi.unstubAllGlobals())

describe('compressImage', () => {
  it('falls back to the original file when canvas/bitmap is unavailable', async () => {
    // jsdom has no createImageBitmap → the helper should swallow it and
    // return the original file untouched.
    const file = new File([new Uint8Array([1, 2, 3])], 'r.png', { type: 'image/png' })
    const out = await compressImage(file)
    expect(out).toBe(file)
  })

  it('returns non-image input unchanged', async () => {
    const notImage = new File(['x'], 'a.txt', { type: 'text/plain' })
    expect(await compressImage(notImage)).toBe(notImage)
  })
})

describe('receiptUrl', () => {
  it('builds a cache-busted url', () => {
    expect(receiptUrl('t1')).toBe('/api/transactions/t1/receipt')
    expect(receiptUrl('t1', 3)).toBe('/api/transactions/t1/receipt?b=3')
  })
})

describe('uploadReceipt', () => {
  it('POSTs the blob with its content-type', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ size: 10 }) })
    vi.stubGlobal('fetch', fetchMock)
    const blob = new Blob([new Uint8Array(10)], { type: 'image/jpeg' })
    await uploadReceipt('t1', blob)
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/transactions/t1/receipt')
    expect(opts.method).toBe('POST')
    expect(opts.headers['content-type']).toBe('image/jpeg')
  })

  it('throws the server detail on failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'Receipt too large' }) }),
    )
    await expect(uploadReceipt('t1', new Blob(['x']))).rejects.toThrow('Receipt too large')
  })
})
