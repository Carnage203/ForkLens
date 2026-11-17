import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import About from './pages/About'
import Cook from './pages/Cook'
import Library from './pages/Library'
import Pantry from './pages/Pantry'
import Profile from './pages/Profile'
import Shared from './pages/Shared'
import Shopping from './pages/Shopping'

// The console is a separate chunk (and charts library) that regular users never download.
const AdminApp = lazy(() => import('./pages/admin/AdminApp'))
// Secret URL segment, set at build time (VITE_ADMIN_PATH). It is not linked anywhere in the UI.
const ADMIN_PATH = import.meta.env.VITE_ADMIN_PATH || '/console-change-me'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Cook />} />
        <Route path="pantry" element={<Pantry />} />
        <Route path="saved" element={<Library />} />
        <Route path="shopping" element={<Shopping />} />
        <Route path="profile" element={<Profile />} />
        <Route path="about" element={<About />} />
        <Route path="r/:token" element={<Shared />} />
        <Route path={ADMIN_PATH.replace(/^\//, '')} element={<Suspense fallback={<Spinner className="mx-auto mt-20 h-8 w-8" />}><AdminApp /></Suspense>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
