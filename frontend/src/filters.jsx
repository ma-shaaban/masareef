import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { useSpace } from './spaces.jsx'

/* Shared category filter (include/exclude id lists), persisted to
   localStorage per space so it survives tab switches and reloads. */
const FilterContext = createContext(null)
const keyFor = (spaceId) => `masareef.filter.${spaceId}`

function loadFilter(spaceId) {
  try {
    const raw = localStorage.getItem(keyFor(spaceId))
    if (raw) {
      const v = JSON.parse(raw)
      return {
        include: Array.isArray(v.include) ? v.include : [],
        exclude: Array.isArray(v.exclude) ? v.exclude : [],
      }
    }
  } catch {
    // corrupt/absent — fall through to empty
  }
  return { include: [], exclude: [] }
}

export function FilterProvider({ children }) {
  const { space } = useSpace()
  const [state, setState] = useState(() => loadFilter(space.id))

  // Load this space's stored filter whenever the active space changes.
  useEffect(() => {
    setState(loadFilter(space.id))
  }, [space.id])

  const setFilter = useCallback(
    (include, exclude) => {
      const next = { include, exclude }
      setState(next)
      try {
        localStorage.setItem(keyFor(space.id), JSON.stringify(next))
      } catch {
        // storage full/blocked — keep it in memory at least
      }
    },
    [space.id],
  )

  const clear = useCallback(() => setFilter([], []), [setFilter])

  return (
    <FilterContext.Provider
      value={{ include: state.include, exclude: state.exclude, setFilter, clear }}
    >
      {children}
    </FilterContext.Provider>
  )
}

export function useCategoryFilter() {
  return useContext(FilterContext)
}
