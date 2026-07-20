import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import CategoryFilter from '../components/CategoryFilter.jsx'

const CATS = [
  { id: 'c1', name: 'Groceries', emoji: '🛒' },
  { id: 'c2', name: 'Comex', emoji: '🪙' },
]

afterEach(cleanup)

describe('CategoryFilter', () => {
  it('cycles neutral → include → exclude → neutral', () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <CategoryFilter categories={CATS} include={[]} exclude={[]} onChange={onChange} />,
    )
    fireEvent.click(screen.getByText('Groceries'))
    expect(onChange).toHaveBeenLastCalledWith(['c1'], [])

    rerender(
      <CategoryFilter categories={CATS} include={['c1']} exclude={[]} onChange={onChange} />,
    )
    fireEvent.click(screen.getByText('Groceries'))
    expect(onChange).toHaveBeenLastCalledWith([], ['c1'])

    rerender(
      <CategoryFilter categories={CATS} include={[]} exclude={['c1']} onChange={onChange} />,
    )
    fireEvent.click(screen.getByText('Groceries'))
    expect(onChange).toHaveBeenLastCalledWith([], [])
  })

  it('supports independent include and exclude selections', () => {
    const onChange = vi.fn()
    render(
      <CategoryFilter categories={CATS} include={['c1']} exclude={['c2']} onChange={onChange} />,
    )
    expect(screen.getByText('Groceries').closest('button').className).toContain('active')
    expect(screen.getByText('Comex').closest('button').className).toContain('exclude')
  })

  it('Clear resets everything and only shows when active', () => {
    const onChange = vi.fn()
    const { rerender } = render(
      <CategoryFilter categories={CATS} include={[]} exclude={[]} onChange={onChange} />,
    )
    expect(screen.queryByText('Clear')).toBeNull()
    rerender(
      <CategoryFilter categories={CATS} include={['c1']} exclude={[]} onChange={onChange} />,
    )
    fireEvent.click(screen.getByText('Clear'))
    expect(onChange).toHaveBeenLastCalledWith([], [])
  })
})
