import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { api } from './api.js'
import CreateSpace from './pages/CreateSpace.jsx'

const SpaceContext = createContext(null)
const STORAGE_KEY = 'masareef.space'

export function SpaceProvider({ children }) {
  const [spaces, setSpaces] = useState(null) // null = loading
  const [spaceId, setSpaceIdState] = useState(() => localStorage.getItem(STORAGE_KEY))

  const refresh = useCallback(async () => {
    const list = await api('/api/spaces')
    setSpaces(list)
    return list
  }, [])

  useEffect(() => {
    refresh().catch(() => setSpaces([]))
  }, [refresh])

  const setSpaceId = useCallback((id) => {
    localStorage.setItem(STORAGE_KEY, id)
    setSpaceIdState(id)
  }, [])

  if (spaces === null) {
    return <div className="splash">Masareef</div>
  }

  const space = spaces.find((s) => s.id === spaceId) || spaces[0] || null

  if (space === null) {
    // First run: no space yet — onboarding before anything else.
    return (
      <div className="authpage">
        <h1>Masareef</h1>
        <p className="sub">Set up your space — a household, shop, or company.</p>
        <CreateSpace
          onCreated={async (created) => {
            await refresh()
            setSpaceId(created.id)
          }}
        />
      </div>
    )
  }

  return (
    <SpaceContext.Provider value={{ space, spaces, setSpaceId, refresh }}>
      {children}
    </SpaceContext.Provider>
  )
}

export function useSpace() {
  return useContext(SpaceContext)
}
