import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { FilterProvider, useCategoryFilter } from '../filters.jsx'

// Controllable space id for the provider (which reads useSpace()).
const h = vi.hoisted(() => ({ spaceId: 's1' }))
vi.mock('../spaces.jsx', () => ({ useSpace: () => ({ space: { id: h.spaceId } }) }))

function Consumer() {
  const { include, exclude, setFilter, clear } = useCategoryFilter()
  return (
    <div>
      <span data-testid="inc">{include.join(',')}</span>
      <span data-testid="exc">{exclude.join(',')}</span>
      <button onClick={() => setFilter(['a'], ['b'])}>set</button>
      <button onClick={clear}>clear</button>
    </div>
  )
}

beforeEach(() => {
  localStorage.clear()
  h.spaceId = 's1'
})
afterEach(cleanup)

describe('FilterProvider', () => {
  it('persists to localStorage per space', () => {
    render(
      <FilterProvider>
        <Consumer />
      </FilterProvider>,
    )
    expect(screen.getByTestId('inc').textContent).toBe('')
    fireEvent.click(screen.getByText('set'))
    expect(screen.getByTestId('inc').textContent).toBe('a')
    expect(screen.getByTestId('exc').textContent).toBe('b')
    expect(JSON.parse(localStorage.getItem('masareef.filter.s1'))).toEqual({
      include: ['a'],
      exclude: ['b'],
    })
  })

  it('isolates filters by space and restores them', () => {
    const { rerender } = render(
      <FilterProvider>
        <Consumer />
      </FilterProvider>,
    )
    fireEvent.click(screen.getByText('set')) // s1 → a / b

    // switch to s2 → empty
    h.spaceId = 's2'
    rerender(
      <FilterProvider>
        <Consumer />
      </FilterProvider>,
    )
    expect(screen.getByTestId('inc').textContent).toBe('')

    // back to s1 → restored from storage
    h.spaceId = 's1'
    rerender(
      <FilterProvider>
        <Consumer />
      </FilterProvider>,
    )
    expect(screen.getByTestId('inc').textContent).toBe('a')
    expect(screen.getByTestId('exc').textContent).toBe('b')
  })

  it('clear empties and persists', () => {
    render(
      <FilterProvider>
        <Consumer />
      </FilterProvider>,
    )
    fireEvent.click(screen.getByText('set'))
    fireEvent.click(screen.getByText('clear'))
    expect(screen.getByTestId('inc').textContent).toBe('')
    expect(JSON.parse(localStorage.getItem('masareef.filter.s1'))).toEqual({
      include: [],
      exclude: [],
    })
  })
})
