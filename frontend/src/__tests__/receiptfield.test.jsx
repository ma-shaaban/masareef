import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('../receipt.js', async (orig) => ({
  ...(await orig()),
  compressImage: vi.fn(async (f) => f),
  uploadReceipt: vi.fn(async () => ({ size: 1 })),
}))

import ReceiptField from '../components/ReceiptField.jsx'
import { uploadReceipt } from '../receipt.js'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function pickFile() {
  const file = new File([new Uint8Array([1, 2, 3])], 'r.jpg', { type: 'image/jpeg' })
  fireEvent.change(screen.getByLabelText('Receipt photo'), { target: { files: [file] } })
  return file
}

describe('ReceiptField (deferred)', () => {
  it('shows the Add button, then a thumbnail after picking, and hands the blob up', async () => {
    globalThis.URL.createObjectURL = vi.fn(() => 'blob:preview')
    globalThis.URL.revokeObjectURL = vi.fn()
    const onPending = vi.fn()
    render(<ReceiptField mode="deferred" onPendingChange={onPending} />)

    expect(screen.getByRole('button', { name: /add receipt/i })).toBeTruthy()
    const file = pickFile()

    await waitFor(() => expect(screen.getByAltText('Receipt')).toBeTruthy())
    expect(onPending).toHaveBeenLastCalledWith(file)
    expect(uploadReceipt).not.toHaveBeenCalled() // deferred: no upload yet

    fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
    expect(onPending).toHaveBeenLastCalledWith(null)
    expect(screen.getByRole('button', { name: /add receipt/i })).toBeTruthy()
  })
})

describe('ReceiptField (live)', () => {
  it('uploads immediately on pick', async () => {
    render(<ReceiptField mode="live" txId="t1" hasReceipt={false} />)
    pickFile()
    await waitFor(() => expect(uploadReceipt).toHaveBeenCalledWith('t1', expect.anything()))
    await waitFor(() => expect(screen.getByAltText('Receipt')).toBeTruthy())
  })

  it('shows an existing receipt thumbnail when hasReceipt is true', () => {
    render(<ReceiptField mode="live" txId="t1" hasReceipt={true} />)
    const img = screen.getByAltText('Receipt')
    expect(img.getAttribute('src')).toContain('/api/transactions/t1/receipt')
  })
})
