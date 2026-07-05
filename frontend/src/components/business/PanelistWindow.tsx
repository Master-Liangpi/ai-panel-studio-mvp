// ============================================================
// PanelistWindow — 嘉宾小窗
// 展示：头像/首字替 / 姓名 / 头衔 / ColorBadge / StatusIndicator
// 主持人置顶橙色边框，固定高度 120px
// ============================================================

import React from 'react'
import { ColorBadge } from '../base/ColorBadge'
import { StatusIndicator } from '../base/StatusIndicator'
import type { Panelist } from '../../types'

interface Props {
  panelist: Panelist
}

export const PanelistWindow: React.FC<Props> = ({ panelist }) => {
  const isHost = panelist.role === 'host'
  const initials = panelist.name.slice(0, 2)

  return (
    <div className={`panelist-window ${isHost ? 'panelist-window--host' : ''}`}>
      <div className="panelist-window__color-bar" style={{ backgroundColor: panelist.color }} />
      <div className="panelist-window__body">
        <div className="panelist-window__avatar" style={{ backgroundColor: panelist.color + '30', color: panelist.color }}>
          {initials}
        </div>
        <div className="panelist-window__info">
          <div className="panelist-window__name-row">
            <span className="panelist-window__name">{panelist.name}</span>
            {isHost && <span className="panelist-window__host-badge">主持</span>}
          </div>
          <span className="panelist-window__title" title={panelist.title}>
            {panelist.title || '嘉宾'}
          </span>
          <StatusIndicator status={panelist.ui_status} />
        </div>
      </div>
    </div>
  )
}
