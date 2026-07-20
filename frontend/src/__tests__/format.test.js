import { describe, expect, it } from 'vitest'
import { addMonths, fmtDay, fmtMoney, monthLabel, monthRange, todayISO } from '../format.js'

describe('fmtMoney', () => {
  it('formats whole EGP amounts without decimals', () => {
    expect(fmtMoney(1250, 'EGP')).toMatch(/1,250/)
  })
  it('keeps cents when present', () => {
    expect(fmtMoney(42.25, 'EGP')).toMatch(/42\.25/)
  })
  it('falls back gracefully on unknown currency codes', () => {
    expect(fmtMoney(10, 'XXX')).toContain('10')
  })
})

describe('dates', () => {
  it('todayISO is a local YYYY-MM-DD', () => {
    expect(todayISO()).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
  it('fmtDay says Today/Yesterday', () => {
    const today = todayISO()
    const y = new Date()
    y.setDate(y.getDate() - 1)
    const yesterday = `${y.getFullYear()}-${String(y.getMonth() + 1).padStart(2, '0')}-${String(y.getDate()).padStart(2, '0')}`
    expect(fmtDay(today)).toBe('Today')
    expect(fmtDay(yesterday)).toBe('Yesterday')
    expect(fmtDay('2020-01-15')).toMatch(/15/)
  })
  it('addMonths rolls over years', () => {
    expect(addMonths('2026-01', -1)).toBe('2025-12')
    expect(addMonths('2026-12', 1)).toBe('2027-01')
    expect(addMonths('2026-07', -3)).toBe('2026-04')
  })
  it('monthRange covers the whole month', () => {
    expect(monthRange('2026-02')).toEqual({ from: '2026-02-01', to: '2026-02-28' })
    expect(monthRange('2024-02').to).toBe('2024-02-29')
    expect(monthRange('2026-07').to).toBe('2026-07-31')
  })
  it('monthLabel is human', () => {
    expect(monthLabel('2026-07')).toMatch(/July 2026/)
  })
})
