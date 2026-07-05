// ============================================================
// ScrollPanel — 独立滚动容器
// 禁止整页滚动，仅此容器内部可滚动
// ============================================================

import React from 'react'

interface Props {
  children: React.ReactNode
  className?: string
  style?: React.CSSProperties
  onScroll?: (e: React.UIEvent<HTMLDivElement>) => void
}

export const ScrollPanel: React.FC<Props> = ({ children, className = '', style, onScroll }) => {
  return (
    <div
      className={`scroll-panel ${className}`}
      style={style}
      onScroll={onScroll}
    >
      {children}
    </div>
  )
}
