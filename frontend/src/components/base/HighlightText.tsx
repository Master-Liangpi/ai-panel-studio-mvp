// ============================================================
// HighlightText — 高亮文本容器
// highlight=true 时背景从品牌色渐变消退（2s），然后恢复正常
// ============================================================

import React, { useEffect, useState } from 'react'

interface Props {
  highlight: boolean
  children: React.ReactNode
  className?: string
}

export const HighlightText: React.FC<Props> = ({ highlight, children, className = '' }) => {
  const [animating, setAnimating] = useState(false)

  useEffect(() => {
    if (highlight) {
      setAnimating(true)
      const timer = setTimeout(() => setAnimating(false), 2200)
      return () => clearTimeout(timer)
    }
  }, [highlight])

  return (
    <div className={`highlight-text ${animating ? 'highlight-text--active' : ''} ${className}`}>
      {children}
    </div>
  )
}
