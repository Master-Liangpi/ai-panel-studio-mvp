import React from 'react'
import { useNavigate } from 'react-router-dom'
import type { Discussion } from '../../types'
import { sanitizeDisplayText } from '../../utils/text'

interface Props {
  discussion: Discussion
}

const STATUS_MAP: Record<string, { label: string; className: string }> = {
  active: { label: '进行中', className: 'tag-active' },
  paused: { label: '已暂停', className: 'tag-paused' },
  completed: { label: '已结束', className: 'tag-completed' },
}

function formatTime(isoStr: string): string {
  const date = new Date(isoStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes} 分钟前`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  return `${days} 天前`
}

export const DiscussionCard: React.FC<Props> = ({ discussion }) => {
  const navigate = useNavigate()
  const statusCfg = STATUS_MAP[discussion.status] || STATUS_MAP.active
  const safeTitle = sanitizeDisplayText(discussion.title, `未命名讨论 #${discussion.id}`)
  const safeTopic = sanitizeDisplayText(discussion.topic, '')

  return (
    <div className="discussion-card" onClick={() => navigate(`/studio/${discussion.id}`)}>
      <div className="discussion-card__header">
        <h3 className="discussion-card__title">{safeTitle}</h3>
        <span className={`discussion-card__tag ${statusCfg.className}`}>
          {statusCfg.label}
        </span>
      </div>
      {safeTopic && <p className="discussion-card__topic">{safeTopic}</p>}
      <div className="discussion-card__meta">
        <span>👥 {discussion.panelist_count} 位嘉宾</span>
        <span>💬 {discussion.speech_count} 条发言</span>
        <span className="discussion-card__time">{formatTime(discussion.updated_at)}</span>
      </div>
    </div>
  )
}
