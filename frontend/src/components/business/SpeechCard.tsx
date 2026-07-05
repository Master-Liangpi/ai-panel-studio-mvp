// ============================================================
// SpeechCard — 单条发言卡片
// 左侧 4px 色条 + 发言人姓名 + 正文 + 相对时间
// 新发言 slideUp 入场动画
// ============================================================

import React from 'react'
import type { Speech } from '../../types'

interface Props {
  speech: Speech
  isStreaming?: boolean  // 流式生成中的半成品
}

function formatRelativeTime(isoStr: string): string {
  const date = new Date(isoStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const sec = Math.floor(diff / 1000)
  if (sec < 10) return '刚刚'
  if (sec < 60) return `${sec} 秒前`
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} 分钟前`
  const hours = Math.floor(min / 60)
  return `${hours} 小时前`
}

export const SpeechCard: React.FC<Props> = ({ speech, isStreaming = false }) => {
  return (
    <div className={`speech-card ${isStreaming ? 'speech-card--streaming' : ''}`}>
      <div className="speech-card__color-bar" style={{ backgroundColor: speech.panelist_color }} />
      <div className="speech-card__body">
        <div className="speech-card__header">
          <span className="speech-card__speaker" style={{ color: speech.panelist_color }}>
            {speech.panelist_name}
          </span>
          <span className="speech-card__seq">#{speech.sequence_num}</span>
        </div>
        <p className="speech-card__content">{speech.content}</p>
        <span className="speech-card__time">{formatRelativeTime(speech.created_at)}</span>
      </div>
    </div>
  )
}
