import { Plug } from 'lucide-react'

import { groupConnectorsByType, type ConnectorLike } from './connectorDisplay'

type ConnectorChipsProps = {
  connectors: ConnectorLike[]
}

export function ConnectorChips({ connectors }: ConnectorChipsProps) {
  const groups = groupConnectorsByType(connectors)
  if (groups.length === 0) {
    return null
  }

  return (
    <div className="connector-chips" aria-label="Conectores">
      {groups.map((group) => (
        <span key={group.type} className="connector-chip">
          <Plug size={12} aria-hidden />
          {group.type} ({group.count})
        </span>
      ))}
    </div>
  )
}
