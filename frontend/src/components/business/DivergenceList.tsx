import React from 'react'
import { ScrollPanel } from '../base/ScrollPanel'
import { DivergenceItem } from './DivergenceItem'
import type { DivergencePoint } from '../../types'

interface Props {
  items: DivergencePoint[]
  highlightIds: Set<string>
}

export const DivergenceList: React.FC<Props> = ({ items, highlightIds }) => {
  return (
    <div className="insight-section">
      <h3 className="insight-section__title">⚡ 分歧</h3>
      <ScrollPanel className="insight-section__scroll">
        {items.length === 0 ? (
          <p className="insight-section__empty">暂未发现分歧</p>
        ) : (
          items.map((d) => (
            <DivergenceItem
              key={d.id}
              divergence={d}
              highlight={highlightIds.has(`divergence-${d.id}`)}
            />
          ))
        )}
      </ScrollPanel>
    </div>
  )
}
