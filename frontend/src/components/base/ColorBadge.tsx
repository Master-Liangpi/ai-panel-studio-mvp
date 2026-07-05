// ============================================================
// ColorBadge — 颜色标签/色块
// 用于嘉宾窗、发言卡片的专属色条
// ============================================================

import React from 'react'

interface Props {
  color: string
  size?: 'sm' | 'md' | 'lg'
  label?: string
  className?: string
}

export const ColorBadge: React.FC<Props> = ({ color, size = 'md', label, className = '' }) => {
  const sizeMap = { sm: 3, md: 4, lg: 6 }
  const width = sizeMap[size]

  return (
    <span className={`color-badge ${className}`} title={label}>
      <span
        className="color-badge__bar"
        style={{
          backgroundColor: color,
          width: `${width}px`,
          minWidth: `${width}px`,
          borderRadius: '2px',
          alignSelf: 'stretch',
        }}
      />
      {label && <span className="color-badge__label">{label}</span>}
    </span>
  )
}
