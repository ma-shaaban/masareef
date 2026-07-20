import { NavLink, Outlet } from 'react-router'
import { useSpace } from '../spaces.jsx'

const TABS = [
  ['/', '➕', 'Add'],
  ['/history', '🧾', 'History'],
  ['/reports', '📊', 'Reports'],
  ['/settings', '⚙️', 'Settings'],
]

export default function Layout() {
  const { space } = useSpace()
  return (
    <div className="app">
      <header className="topbar">
        <h1>Masareef</h1>
        <span className="space-name">{space.name}</span>
      </header>
      <Outlet />
      <nav className="tabbar">
        {TABS.map(([to, icon, label]) => (
          <NavLink key={to} to={to} end={to === '/'}>
            <span className="icon">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
