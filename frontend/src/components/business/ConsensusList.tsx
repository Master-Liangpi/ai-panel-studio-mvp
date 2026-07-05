// ============================================================
// ConsensusList — 共识列表
// ============================================================

import React from 'react'
import { ScrollPanel } from '../base/ScrollPanel'
import { ConsensusItem } from './ConsensusItem'
import type { ConsensusPoint } from '../../types'

interface Props {
  items: ConsensusPoint[]
  highlightIds: Set<string>
}

export const ConsensusList: React.FC<Props> = ({ items, highlightIds }) => {
  return (
    <div className="insight-section">
      <h3 className="insight-section__title">🤝 共识</h3>
      <ScrollPanel className="insight-section__scroll">
        {items.length === 0 ? (
          <p className="insight-section__empty">暂未形成共识</p>
        ) : (
          items.map((c) => (
            <ConsensusItem
              key={c.id}
              consensus={c}
              highlight={highlightIds.has(`consensus-${c.id}`)}
            />
          ))
        )}
      </ScrollPanel>
    </div>
  )
}
