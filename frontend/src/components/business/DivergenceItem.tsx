import React from 'react'
import { HighlightText } from '../base/HighlightText'
import type { DivergencePoint } from '../../types'

interface Props {
  divergence: DivergencePoint
  highlight: boolean
}

export const DivergenceItem: React.FC<Props> = ({ divergence, highlight }) => {
  return (
    <HighlightText highlight={highlight}>
      <div className={`insight-item insight-item--divergence ${divergence.resolved ? 'insight-item--resolved' : ''}`}>
        <div className="insight-item__header">
          <span className="insight-item__icon">⚡</span>
          <h4 className="insight-item__topic">{divergence.topic}</h4>
          {divergence.resolved && <span className="insight-item__resolved-tag">已消解</span>}
        </div>
        <p className="insight-item__content">{divergence.content}</p>
        {divergence.sides && <p className="insight-item__sides">{divergence.sides}</p>}
        <span className="insight-item__time">
          {new Date(divergence.updated_at).toLocaleTimeString('zh-CN', {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </span>
      </div>
    </HighlightText>
  )
}
