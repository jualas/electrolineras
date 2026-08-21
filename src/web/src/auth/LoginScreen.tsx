import { LoginPanel } from './LoginPanel'

export function LoginScreen({ loginEnabled }: { loginEnabled: boolean }) {
  return (
    <div className="login-screen">
      <div className="login-screen__card">
        <p className="login-screen__brand">Electrolineras</p>
        {loginEnabled ? (
          <LoginPanel />
        ) : (
          <p className="assistant-panel__muted">
            Falta configurar TOTP en el servidor. Ver <code>scripts/auth/setup_private_auth.py</code>.
          </p>
        )}
      </div>
    </div>
  )
}
