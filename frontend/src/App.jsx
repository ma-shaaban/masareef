import { Suspense, lazy } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router'
import { AuthProvider, RequireAuth } from './auth.jsx'
import Layout from './components/Layout.jsx'
import Add from './pages/Add.jsx'
import History from './pages/History.jsx'
import Invite from './pages/Invite.jsx'
import Login from './pages/Login.jsx'
import Settings from './pages/Settings.jsx'
import Signup from './pages/Signup.jsx'
import { SpaceProvider } from './spaces.jsx'
import { FilterProvider } from './filters.jsx'

// Reports pulls in the charting library — keep it out of the initial bundle
// so the quick-add screen loads fast on the phone.
const Reports = lazy(() => import('./pages/Reports.jsx'))

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/signup" element={<Signup />} />
          {/* Invite acceptance must work before the user has any space, so it
              lives OUTSIDE SpaceProvider (which otherwise shows onboarding and
              never renders its children for a space-less user). */}
          <Route
            path="/invite/:code"
            element={
              <RequireAuth>
                <Invite />
              </RequireAuth>
            }
          />
          <Route
            element={
              <RequireAuth>
                <SpaceProvider>
                  <FilterProvider>
                    <Layout />
                  </FilterProvider>
                </SpaceProvider>
              </RequireAuth>
            }
          >
            <Route path="/" element={<Add />} />
            <Route path="/history" element={<History />} />
            <Route
              path="/reports"
              element={
                <Suspense fallback={<p className="hint">Loading reports…</p>}>
                  <Reports />
                </Suspense>
              }
            />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
