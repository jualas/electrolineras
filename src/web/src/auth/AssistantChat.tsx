import { useEffect, useRef, useState } from 'react'

import { fetchTripChat } from '../api/auth'
import type { TripChatMessage, TripChatOverrides } from '../api/types'

export type AssistantChatChip = {
  id: string
  label: string
  message: string
}

const DEFAULT_CHIPS: AssistantChatChip[] = [
  { id: 'why_stop', label: '¿Por qué esta parada?', message: '¿Por qué elegiste estas paradas?' },
  { id: 'avoid_tolls', label: 'Evitar peajes', message: 'Quiero evitar peajes' },
  { id: 'fastest', label: 'Ruta más rápida', message: 'Prefiero la ruta más rápida por autopista' },
  { id: 'cheaper', label: 'Más barata', message: 'Prioriza cargadores más baratos' },
  { id: 'fewer_stops', label: 'Parar menos', message: 'Quiero parar menos veces, aunque cargue más en cada parada' },
  { id: 'less_charge', label: 'Cargar menos / parada', message: 'Carga menos en cada parada (zona rápida DC)' },
]

type AssistantChatProps = {
  planSnapshot: Record<string, unknown> | null | undefined
  disabled?: boolean
  onApplyOverrides: (overrides: TripChatOverrides) => void | Promise<void>
}

export function AssistantChat({ planSnapshot, disabled, onApplyOverrides }: AssistantChatProps) {
  const [messages, setMessages] = useState<TripChatMessage[]>([
    {
      role: 'assistant',
      content:
        'El plan está en el mapa y en el panel. ¿Qué quieres cambiar? Usa un chip o escribe en una frase.',
    },
  ])
  const [draft, setDraft] = useState('')
  const [chips, setChips] = useState<AssistantChatChip[]>(DEFAULT_CHIPS)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }, [messages, loading])

  async function sendMessage(text: string) {
    const content = text.trim()
    if (!content || loading || disabled) {
      return
    }
    setError(null)
    const userMsg: TripChatMessage = { role: 'user', content }
    const nextHistory = [...messages, userMsg]
    setMessages(nextHistory)
    setDraft('')
    setLoading(true)
    try {
      const result = await fetchTripChat({
        message: content,
        history: messages,
        planSnapshot: planSnapshot ?? null,
      })
      if (result.chips?.length) {
        setChips(
          result.chips.map((chip) => ({
            id: chip.id,
            label: chip.label,
            message: chip.message,
          })),
        )
      }
      setMessages((prev) => [...prev, { role: 'assistant', content: result.reply }])
      if (result.needs_replan && result.overrides && Object.keys(result.overrides).length > 0) {
        await onApplyOverrides(result.overrides)
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'No se pudo contactar con el asistente'
      setError(msg)
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'No pude responder ahora. Reintenta o usa el formulario de preferencias.' },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="assistant-chat">
      <div className="assistant-chat__header">
        <h3 className="assistant-chat__title">Chat del viaje</h3>
        <span className="assistant-chat__badge">IA · interacción</span>
      </div>
      <p className="assistant-chat__hint">
        El detalle del plan lo ves arriba. Aquí solo cambios y dudas puntuales.
      </p>
      <div className="assistant-chat__chips" role="group" aria-label="Acciones rápidas">
        {chips.map((chip) => (
          <button
            key={chip.id}
            type="button"
            className="assistant-chat__chip"
            disabled={disabled || loading}
            onClick={() => void sendMessage(chip.message)}
          >
            {chip.label}
          </button>
        ))}
      </div>
      <div className="assistant-chat__thread" aria-live="polite">
        {messages.map((msg, index) => (
          <div
            key={`${msg.role}-${index}`}
            className={`assistant-chat__bubble assistant-chat__bubble--${msg.role}`}
          >
            {msg.content}
          </div>
        ))}
        {loading && <div className="assistant-chat__bubble assistant-chat__bubble--assistant">Pensando…</div>}
        <div ref={bottomRef} />
      </div>
      {error && (
        <p className="route-message route-message--error" role="alert">
          {error}
        </p>
      )}
      <form
        className="assistant-chat__composer"
        onSubmit={(event) => {
          event.preventDefault()
          void sendMessage(draft)
        }}
      >
        <input
          type="text"
          className="assistant-chat__input"
          placeholder="Ej.: evita peajes, parar menos…"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          disabled={disabled || loading}
          maxLength={2000}
        />
        <button type="submit" className="btn btn--primary" disabled={disabled || loading || !draft.trim()}>
          Enviar
        </button>
      </form>
    </div>
  )
}
