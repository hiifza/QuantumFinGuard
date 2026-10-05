import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { AppShell } from './components/layout/AppShell'
import { LoginPage } from './pages/LoginPage'
import { OverviewPage } from './pages/OverviewPage'
import { TransactionsPage } from './pages/TransactionsPage'
import { InvestigationPage } from './pages/InvestigationPage'
import { NotYetBuiltPage } from './pages/NotYetBuiltPage'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center" style={{ background: 'var(--bg)', color: 'var(--text-dim)' }}>
        Loading session…
      </div>
    )
  }
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <AppShell>{children}</AppShell>
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route path="/overview" element={<ProtectedLayout><OverviewPage /></ProtectedLayout>} />
      <Route path="/transactions" element={<ProtectedLayout><TransactionsPage /></ProtectedLayout>} />
      <Route path="/investigation" element={<ProtectedLayout><InvestigationPage /></ProtectedLayout>} />
      <Route path="/investigation/:transactionId" element={<ProtectedLayout><InvestigationPage /></ProtectedLayout>} />

      <Route path="/fraud" element={<ProtectedLayout><NotYetBuiltPage title="Fraud & Risk" /></ProtectedLayout>} />
      <Route path="/behavioral" element={<ProtectedLayout><NotYetBuiltPage title="Behavioral Intelligence" /></ProtectedLayout>} />
      <Route path="/blockchain" element={<ProtectedLayout><NotYetBuiltPage title="Blockchain Explorer" /></ProtectedLayout>} />
      <Route path="/copilot" element={<ProtectedLayout><NotYetBuiltPage title="AI Investigation Copilot" /></ProtectedLayout>} />
      <Route path="/security" element={<ProtectedLayout><NotYetBuiltPage title="Security Center" /></ProtectedLayout>} />
      <Route path="/security/pqc" element={<ProtectedLayout><NotYetBuiltPage title="Quantum-Safe Security" /></ProtectedLayout>} />
      <Route path="/security/audit" element={<ProtectedLayout><NotYetBuiltPage title="Audit Trail" /></ProtectedLayout>} />
      <Route path="/data" element={<ProtectedLayout><NotYetBuiltPage title="Dataset Status" /></ProtectedLayout>} />

      <Route path="/" element={<Navigate to="/overview" replace />} />
      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
