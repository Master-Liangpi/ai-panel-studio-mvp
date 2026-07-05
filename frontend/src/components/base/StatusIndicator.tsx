// ============================================================
// StatusIndicator — 嘉宾状态指示灯
// idle=灰色常亮 / preparing=黄色慢脉冲 / speaking=绿色呼吸+声纹
// ============================================================

import React from 'react'
import type { PanelistStatus } from '../../types'

interface Props {
  status: PanelistStatus
  size?: number
}

const STATUS_CONFIG: Record<PanelistStatus, { color: string; label: string; className: string }> = {
  idle:       { color: '#95A5A6', label: '待机',   className: 'status-idle' },
  preparing:  { color: '#F39C12', label: '准备中', className: 'status-preparing' },
  speaking:   { color: '#27AE60', label: '发言中', className: 'status-speaking' },
  offline:    { color: 'transparent', label: '已离场', className: 'status-offline' },
}

export const StatusIndicator: React.FC<Props> = ({ status, size = 8 }) => {
  const cfg = STATUS_CONFIG[status]

  if (status === 'offline') {
    return (
      <span className="status-indicator status-offline">
        <span className="status-indicator__label">{cfg.label}</span>
      </span>
    )
  }

  return (
    <span className={`status-indicator ${cfg.className}`} title={cfg.label}>
      <span
        className="status-indicator__dot"
        style={{
          width: size,
          height: size,
          backgroundColor: cfg.color,
        }}
      />
      {status === 'speaking' && (
        <>
          <span className="status-indicator__ripple status-indicator__ripple--1" style={{ borderColor: cfg.color }} />
          <span className="status-indicator__ripple status-indicator__ripple--2" style={{ borderColor: cfg.color }} />
        </>
      )}
      <span className="status-indicator__label">{cfg.label}</span>
    </span>
  )
}
