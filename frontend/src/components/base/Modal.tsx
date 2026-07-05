// ============================================================
// Modal — 通用弹窗
// 入场 scale 动画 + 遮罩点击关闭 + ESC 关闭
// ============================================================

import React, { useEffect } from 'react'

interface Props {
  visible: boolean
  title: string
  width?: number
  onClose: () => void
  children: React.ReactNode
  maskClosable?: boolean
}

export const Modal: React.FC<Props> = ({
  visible,
  title,
  width = 480,
  onClose,
  children,
  maskClosable = true,
}) => {
  useEffect(() => {
    if (!visible) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [visible, onClose])

  if (!visible) return null

  return (
    <div
      className="modal-overlay"
      onClick={maskClosable ? onClose : undefined}
    >
      <div
        className="modal-content"
        style={{ width: `${width}px`, maxWidth: '90vw' }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <h2 className="modal-title">{title}</h2>
          <button className="modal-close" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </div>
        <div className="modal-body">{children}</div>
      </div>
    </div>
  )
}
