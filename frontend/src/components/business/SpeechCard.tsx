import React from 'react'
import type { Speech } from '../../types'
import { sanitizeDisplayText } from '../../utils/text'

interface Props {
  speech: Speech
  isStreaming?: boolean
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
  const speakerName = sanitizeDisplayText(speech.panelist_name, '匿名嘉宾')

  return (
    <div className={`speech-card ${isStreaming ? 'speech-card--streaming' : ''}`}>
      <div className="speech-card__color-bar" style={{ backgroundColor: speech.panelist_color }} />
      <div className="speech-card__body">
        <div className="speech-card__header">
          <span className="speech-card__speaker" style={{ color: speech.panelist_color }}>
            {speakerName}
          </span>
          <span className="speech-card__seq">#{speech.sequence_num}</span>
        </div>
        <p className="speech-card__content">{speech.content}</p>
        <span className="speech-card__time">{formatRelativeTime(speech.created_at)}</span>
      </div>
    </div>
  )
}
