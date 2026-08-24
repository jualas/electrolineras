import { useState, type FormEvent } from 'react'

import { useAuth } from './AuthContext'
import { getLastUsername } from './lastUsername'

export function LoginPanel() {
  const { login } = useAuth()
  const [username, setUsername] = useState(getLastUsername)
  const [totpCode, setTotpCode] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login(username.trim(), totpCode.replace(/\s/g, ''))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo iniciar sesión')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="panel search-panel auth-panel">
      <h2>Zona privada</h2>
      <p className="panel-hint">
        Usuario y código de 6 dígitos de Microsoft Authenticator (u otro TOTP). Sin contraseña aparte.
      </p>
      <form className="route-form" onSubmit={handleSubmit}>
        <label className="field">
          <span className="field__label">Usuario</span>
          <input
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </label>
        <label className="field">
          <span className="field__label">Código Authenticator</span>
          <input
            type="text"
            inputMode="numeric"
            pattern="[0-9 ]{6,8}"
            autoComplete="one-time-code"
            placeholder="123456"
            value={totpCode}
            onChange={(e) => setTotpCode(e.target.value)}
            required
          />
        </label>
        {error && (
          <p className="route-message route-message--error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn--primary" disabled={submitting}>
          {submitting ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </section>
  )
}
