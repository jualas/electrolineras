import { useState, type FormEvent } from 'react'

import { useAuth } from './AuthContext'

export function LoginPanel() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
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
    <section className="auth-panel">
      <h2 className="auth-panel__title">Zona privada</h2>
      <p className="auth-panel__hint">
        Usuario y código de 6 dígitos de Microsoft Authenticator (u otro TOTP). Sin contraseña aparte.
      </p>
      <form className="auth-form" onSubmit={handleSubmit}>
        <label className="auth-form__field">
          <span>Usuario</span>
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
        <label className="auth-form__field">
          <span>Código Authenticator</span>
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
        {error && <p className="auth-form__error" role="alert">{error}</p>}
        <button type="submit" className="auth-form__submit" disabled={submitting}>
          {submitting ? 'Entrando…' : 'Entrar'}
        </button>
      </form>
    </section>
  )
}
