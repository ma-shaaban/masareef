import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CategoryFilterSheet from '../components/CategoryFilterSheet.jsx'

const CATS = [
  { id: 'c1', name: 'Groceries', emoji: '🛒' },
  { id: 'c2', name: 'Comex', emoji: '🪙' },
  { id: 'c3', name: 'Charity', emoji: '🤲' },
]

afterEach(cleanup)

function open(props = {}) {
  const onChange = vi.fn()
  render(
    <CategoryFilterSheet
      categories={CATS}
      include={[]}
      exclude={[]}
      onChange={onChange}
      {...props}
    />,
  )
  fireEvent.click(screen.getByRole('button', { name: /filter/i }))
  return onChange
}

describe('CategoryFilterSheet', () => {
  it('is collapsed until the button is clicked', () => {
    render(<CategoryFilterSheet categories={CATS} include={[]} exclude={[]} onChange={vi.fn()} />)
    expect(screen.queryByText('Groceries')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: /filter/i }))
    expect(screen.getByText('Groceries')).toBeTruthy()
  })

  it('search narrows the list', () => {
    open()
    fireEvent.change(screen.getByLabelText('Search categories'), { target: { value: 'cha' } })
    expect(screen.getByText('Charity')).toBeTruthy()
    expect(screen.queryByText('Groceries')).toBeNull()
    expect(screen.queryByText('Comex')).toBeNull()
  })

  it('tapping a row cycles include → exclude → clear', () => {
    const onChange = open()
    fireEvent.click(screen.getByText('Groceries'))
    expect(onChange).toHaveBeenLastCalledWith(['c1'], [])
    cleanup()

    const onChange2 = open({ include: ['c1'] })
    fireEvent.click(screen.getByText('Groceries'))
    expect(onChange2).toHaveBeenLastCalledWith([], ['c1'])
    cleanup()

    const onChange3 = open({ exclude: ['c1'] })
    fireEvent.click(screen.getByText('Groceries'))
    expect(onChange3).toHaveBeenLastCalledWith([], [])
  })

  it('shows the active count and Clear resets', () => {
    render(
      <CategoryFilterSheet
        categories={CATS}
        include={['c1']}
        exclude={['c2']}
        onChange={vi.fn()}
      />,
    )
    expect(screen.getByRole('button', { name: /2 active/i })).toBeTruthy()
    const onChange = vi.fn()
    cleanup()
    render(
      <CategoryFilterSheet categories={CATS} include={['c1']} exclude={[]} onChange={onChange} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /filter/i }))
    fireEvent.click(screen.getByRole('button', { name: 'Clear' }))
    expect(onChange).toHaveBeenLastCalledWith([], [])
  })
})
