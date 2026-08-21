import { AuthProvider, useAuth } from './auth/AuthContext'
import { LoginScreen } from './auth/LoginScreen'
import { AppShell } from './components/layout/AppShell'

function Gate() {
  const { loading, privateStackEnabled, loginEnabled, authenticated } = useAuth()
  if (loading) {
    return null
  }
  if (privateStackEnabled && !authenticated) {
    return <LoginScreen loginEnabled={loginEnabled} />
  }
  return <AppShell />
}

export default function App() {
  return (
    <AuthProvider>
      <Gate />
    </AuthProvider>
  )
}
