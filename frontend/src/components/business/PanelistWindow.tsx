import React from 'react'
import { StatusIndicator } from '../base/StatusIndicator'
import type { Panelist } from '../../types'
import { sanitizeDisplayText } from '../../utils/text'

interface Props {
  panelist: Panelist
}

export const PanelistWindow: React.FC<Props> = ({ panelist }) => {
  const isHost = panelist.role === 'host'
  const name = sanitizeDisplayText(panelist.name, isHost ? '主持人' : '未命名嘉宾')
  const title = sanitizeDisplayText(panelist.title, isHost ? '圆桌主持' : '特邀嘉宾')
  const initials = name.slice(0, 2)

  return (
    <div className={`panelist-window ${isHost ? 'panelist-window--host' : ''}`}>
      <div className="panelist-window__color-bar" style={{ backgroundColor: panelist.color }} />
      <div className="panelist-window__body">
        <div className="panelist-window__avatar" style={{ backgroundColor: `${panelist.color}30`, color: panelist.color }}>
          {initials}
        </div>
        <div className="panelist-window__info">
          <div className="panelist-window__name-row">
            <span className="panelist-window__name">{name}</span>
            {isHost && <span className="panelist-window__host-badge">主持</span>}
          </div>
          <span className="panelist-window__title" title={title}>
            {title}
          </span>
          <StatusIndicator status={panelist.ui_status} />
        </div>
      </div>
    </div>
  )
}
