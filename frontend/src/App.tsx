import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { AnalysisProvider } from './context/AnalysisContext'
import AppShell from './components/layout/AppShell'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import ProjectsPage from './pages/ProjectsPage'
import ProjectWorkspacePage from './pages/ProjectWorkspacePage'
import AnalysisPage from './pages/AnalysisPage'
import AskPage from './pages/AskPage'
import KnowledgeBasePage from './pages/KnowledgeBasePage'
import SafetyPage from './pages/SafetyPage'

function Guards() {
  const { user } = useAuth()
  if (!user) return <Routes><Route path="*" element={<LoginPage />} /></Routes>
  return (
    <AppShell>
      <Routes>
        <Route path="/"                        element={<DashboardPage />} />
        <Route path="/projects"                element={<ProjectsPage />} />
        <Route path="/projects/:id/workspace"  element={<ProjectWorkspacePage />} />
        <Route path="/analysis"                element={<AnalysisPage />} />
        <Route path="/ask"                     element={<AskPage />} />
        <Route path="/knowledge-base"          element={<KnowledgeBasePage />} />
        <Route path="/safety"                  element={<SafetyPage />} />
        <Route path="*"                        element={<Navigate to="/" />} />
      </Routes>
    </AppShell>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AnalysisProvider>
        <BrowserRouter>
          <Guards />
        </BrowserRouter>
      </AnalysisProvider>
    </AuthProvider>
  )
}
