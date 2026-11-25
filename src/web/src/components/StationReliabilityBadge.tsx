import { useState } from 'react'
import { AlertTriangle, CheckCircle2, ExternalLink, RefreshCw, ShieldAlert } from 'lucide-react'

import { fetchStationReliability } from '../api/reliability'
import type { StationReliabilityResponse } from '../api/types'

type StationReliabilityBadgeProps = {
  stationId: string
  initial?: StationReliabilityResponse | null
}

const LEVEL_COLORS: Record<StationReliabilityResponse['level'], { bg: string; fg: string; label: string }> = {
  high: { bg: '#ecfdf5', fg: '#047857', label: 'Alta fiabilidad' },
  medium: { bg: '#fffbeb', fg: '#b45309', label: 'Precaución' },
  low: { bg: '#fef2f2', fg: '#b91c1c', label: 'No fiable' },
}

export function StationReliabilityBadge({ stationId, initial = null }: StationReliabilityBadgeProps) {
  const [report, setReport] = useState<StationReliabilityResponse | null>(initial)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleVerifyLive = async () => {
    setLoading(true)
    setError(null)
    try {
      const next = await fetchStationReliability(stationId, { verifyGoogle: true })
      setReport(next)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error al verificar en vivo')
    } finally {
      setLoading(false)
    }
  }

  const badge = report ? LEVEL_COLORS[report.level] : null

  return (
    <div
      style={{
        marginTop: '0.5rem',
        padding: '0.45rem 0.6rem',
        borderRadius: '8px',
        background: badge ? badge.bg : 'rgba(15, 23, 42, 0.04)',
        border: `1px solid ${badge ? badge.fg + '33' : 'rgba(15, 23, 42, 0.12)'}`,
        fontSize: '0.8rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
        {report && badge ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: badge.fg, fontWeight: 600 }}>
            {report.level === 'high' ? (
              <CheckCircle2 size={14} aria-hidden />
            ) : report.level === 'low' ? (
              <ShieldAlert size={14} aria-hidden />
            ) : (
              <AlertTriangle size={14} aria-hidden />
            )}
            {badge.label}
          </span>
        ) : (
          <span style={{ color: '#475569' }}>Estado en vivo sin cruzar</span>
        )}
        <button
          type="button"
          onClick={() => void handleVerifyLive()}
          disabled={loading}
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.25rem',
            padding: '0.2rem 0.5rem',
            borderRadius: '6px',
            border: '1px solid rgba(15, 23, 42, 0.2)',
            background: '#ffffff',
            color: '#0f172a',
            fontSize: '0.75rem',
            cursor: loading ? 'wait' : 'pointer',
          }}
        >
          <RefreshCw size={12} aria-hidden />
          {loading ? 'Comprobando…' : report?.google_checked ? 'Re-verificar Google' : 'Verificar Google'}
        </button>
      </div>

      {report && (
        <div style={{ marginTop: '0.35rem', color: '#1e293b', lineHeight: 1.35 }}>
          <p style={{ margin: 0 }}>{report.summary}</p>
          {report.google_matched && (
            <p style={{ margin: '0.2rem 0 0', color: '#334155', fontSize: '0.75rem' }}>
              Google Places:
              {report.google_available_count != null
                ? ` ${report.google_available_count}/${report.google_total_connectors ?? '?'} libres`
                : ' sin conteo libre'}
              {report.google_out_of_service_count != null && report.google_out_of_service_count > 0
                ? ` · ${report.google_out_of_service_count} averiado(s)`
                : ''}
              {report.google_rating != null
                ? ` · ${report.google_rating.toFixed(1)}/5 (${report.google_rating_count ?? 0})`
                : ''}
            </p>
          )}
          {report.isolated_area ? (
            <p style={{ margin: '0.25rem 0 0', color: '#b45309', fontWeight: 600, fontSize: '0.75rem' }}>
              Sin otro cargador rápido en {report.isolation_radius_km.toFixed(0)} km (zona aislada).
            </p>
          ) : report.backup_station_km != null ? (
            <p style={{ margin: '0.2rem 0 0', color: '#475569', fontSize: '0.74rem' }}>
              Plan B cercano: {report.backup_station_label ?? 'alternativa'} a {report.backup_station_km.toFixed(1)} km.
            </p>
          ) : null}
          {report.google_maps_uri && (
            <a
              href={report.google_maps_uri}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.25rem',
                marginTop: '0.25rem',
                color: '#1d4ed8',
                fontSize: '0.75rem',
                textDecoration: 'none',
              }}
            >
              Ver reseñas en Google Maps <ExternalLink size={11} aria-hidden />
            </a>
          )}
        </div>
      )}
      {error && <p style={{ margin: '0.25rem 0 0', color: '#b91c1c', fontSize: '0.75rem' }}>{error}</p>}
    </div>
  )
}
