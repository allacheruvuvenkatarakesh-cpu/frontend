import { Route, Routes } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout.jsx'
import ProtectedRoute from './components/layout/ProtectedRoute.jsx'
import AnalysisPage from './pages/AnalysisPage.jsx'
import AuthenticityPage from './pages/AuthenticityPage.jsx'
import FingerprintPage from './pages/FingerprintPage.jsx'
import GraphPage from './pages/GraphPage.jsx'
import ProfilePage from './pages/ProfilePage.jsx'
import ComparePage from './pages/ComparePage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import LandingPage from './pages/LandingPage.jsx'
import { LoginPage, RegisterPage } from './pages/AuthPages.jsx'
import NotFoundPage from './pages/NotFoundPage.jsx'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute><AppLayout /></ProtectedRoute>}>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/analysis/:videoId" element={<AnalysisPage />} />
        <Route path="/analysis/:videoId/fingerprint" element={<FingerprintPage />} />
        <Route path="/analysis/:videoId/authenticity" element={<AuthenticityPage />} />
        <Route path="/analysis/:videoId/graph" element={<GraphPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/compare" element={<ComparePage />} />
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
