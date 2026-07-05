import React from 'react'
import { HighlightText } from '../base/HighlightText'
import type { ConsensusPoint } from '../../types'

interface Props {
  consensus: ConsensusPoint
  highlight: boolean
}

export const ConsensusItem: React.FC<Props> = ({ consensus, highlight }) => {
  return (
    <HighlightText highlight={highlight}>
      <div className="insight-item insight-item--consensus">
        <div className="insight-item__header">
          <span className="insight-item__icon">🤝</span>
          <h4 className="insight-item__topic">{consensus.topic}</h4>
        </div>
        <p className="insight-item__content">{consensus.content}</p>
        <span className="insight-item__time">
          {new Date(consensus.updated_at).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>
    </HighlightText>
  )
}
