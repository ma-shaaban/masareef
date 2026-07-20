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
          <Route
            element={
              <RequireAuth>
                <SpaceProvider>
                  <Layout />
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
            <Route path="/invite/:code" element={<Invite />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
