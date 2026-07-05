// ============================================================
// SseStatusBar — SSE 连接状态条
// 演播厅顶部的 2px 细条：
//   connected=绿色 / connecting=黄色闪烁 / disconnected=红色+重连提示
// ============================================================

import React from 'react'

type SSEStatus = 'connecting' | 'connected' | 'disconnected'

interface Props {
  status: SSEStatus
  onReconnect?: () => void
}

const STATUS_MAP: Record<SSEStatus, { color: string; className: string; text: string }> = {
  connected:    { color: '#27AE60', className: 'sse-connected',    text: '实时连接' },
  connecting:   { color: '#F39C12', className: 'sse-connecting',   text: '连接中…' },
  disconnected: { color: '#E74C3C', className: 'sse-disconnected', text: '连接断开 — 点击重连' },
}

export const SseStatusBar: React.FC<Props> = ({ status, onReconnect }) => {
  const cfg = STATUS_MAP[status]

  return (
    <div
      className={`sse-status-bar ${cfg.className}`}
      style={{ '--sse-color': cfg.color } as React.CSSProperties}
      onClick={status === 'disconnected' ? onReconnect : undefined}
      title={cfg.text}
    >
      <span className="sse-status-bar__indicator" />
      <span className="sse-status-bar__text">{cfg.text}</span>
    </div>
  )
}
