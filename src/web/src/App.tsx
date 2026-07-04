import { AuthProvider } from './auth/AuthContext'
import { AppShell } from './components/layout/AppShell'

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  )
}
