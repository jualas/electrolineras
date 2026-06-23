import { useEffect, useState } from 'react'
import './App.css'

const apiUrl = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

function App() {
  const [apiStatus, setApiStatus] = useState<'loading' | 'ok' | 'error'>('loading')

  useEffect(() => {
    fetch(`${apiUrl}/health`)
      .then((res) => (res.ok ? setApiStatus('ok') : setApiStatus('error')))
      .catch(() => setApiStatus('error'))
  }, [])

  return (
    <main className="app">
      <header>
        <h1>Electrolineras</h1>
        <p>Mapa peninsular de puntos de recarga — MVP en desarrollo</p>
      </header>
      <section className="status">
        <p>
          API ({apiUrl}):{' '}
          {apiStatus === 'loading' && 'comprobando…'}
          {apiStatus === 'ok' && 'conectada'}
          {apiStatus === 'error' && 'no disponible (¿arrancaste make api?)'}
        </p>
      </section>
    </main>
  )
}

export default App
