import type { ReactNode } from 'react'

type ReveStatRowProps = {
  icon: ReactNode
  label: string
  value: string
}

export function ReveStatRow({ icon, label, value }: ReveStatRowProps) {
  return (
    <div className="reve-stat-row">
      <span className="reve-stat-row__label">
        {icon}
        {label}
      </span>
      <span className="reve-stat-row__value">{value}</span>
    </div>
  )
}
