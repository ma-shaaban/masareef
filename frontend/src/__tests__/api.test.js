import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, ApiError, authEvents } from '../api.js'

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('api', () => {
  it('returns parsed json on success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(200, { hello: 'world' })))
    expect(await api('/api/x')).toEqual({ hello: 'world' })
  })

  it('returns null on 204', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(204, null)))
    expect(await api('/api/x', { method: 'DELETE' })).toBeNull()
  })

  it('serializes body and sets content-type', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, {}))
    vi.stubGlobal('fetch', fetchMock)
    await api('/api/x', { method: 'POST', body: { a: 1 } })
    const [, opts] = fetchMock.mock.calls[0]
    expect(opts.body).toBe('{"a":1}')
    expect(opts.headers['content-type']).toBe('application/json')
  })

  it('throws ApiError with the server detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse(400, { detail: 'Please enter an amount' })),
    )
    await expect(api('/api/x')).rejects.toMatchObject({
      status: 400,
      message: 'Please enter an amount',
    })
  })

  it('emits auth:required on 401', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse(401, { detail: 'nope' })))
    const seen = vi.fn()
    authEvents.addEventListener('auth:required', seen)
    await expect(api('/api/x')).rejects.toBeInstanceOf(ApiError)
    expect(seen).toHaveBeenCalledOnce()
  })

  it('wraps network failures as status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')))
    await expect(api('/api/x')).rejects.toMatchObject({ status: 0 })
  })
})
