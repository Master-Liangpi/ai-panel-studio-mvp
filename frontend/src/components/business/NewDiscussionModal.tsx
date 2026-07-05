// ============================================================
// NewDiscussionModal — 新建圆桌弹窗
// 表单：标题（必填）+ 议题（选填）→ POST /discussions
// ============================================================

import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Modal } from '../base/Modal'
import { useDiscussionListStore } from '../../store/discussionStore'

interface Props {
  visible: boolean
  onClose: () => void
}

export const NewDiscussionModal: React.FC<Props> = ({ visible, onClose }) => {
  const [title, setTitle] = useState('')
  const [topic, setTopic] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const createDiscussion = useDiscussionListStore((s) => s.createDiscussion)

  const canSubmit = title.trim().length > 0 && !submitting

  const handleSubmit = async () => {
    if (!canSubmit) return
    setError('')
    setSubmitting(true)
    try {
      const id = await createDiscussion(title.trim(), topic.trim() || undefined)
      onClose()
      setTitle('')
      setTopic('')
      navigate(`/studio/${id}`)
    } catch (e: any) {
      setError(e.message || '创建失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && canSubmit) handleSubmit()
  }

  return (
    <Modal visible={visible} title="新建圆桌讨论" onClose={onClose}>
      <div className="new-discussion-form">
        <label className="form-label">
          讨论标题 <span className="required">*</span>
        </label>
        <input
          className="form-input"
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="例如：AI 监管应由政府主导还是行业自律？"
          maxLength={200}
          autoFocus
        />
        <label className="form-label">议题描述（选填）</label>
        <textarea
          className="form-textarea"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="简述讨论背景和核心议题…"
          maxLength={2000}
          rows={3}
        />
        {error && <p className="form-error">{error}</p>}
        <button
          className="btn btn-primary btn-full"
          disabled={!canSubmit}
          onClick={handleSubmit}
        >
          {submitting ? '创建中…' : '创建讨论'}
        </button>
      </div>
    </Modal>
  )
}
