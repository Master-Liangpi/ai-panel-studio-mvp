import React, { useRef, useEffect, useState, useCallback } from 'react'
import { ScrollPanel } from '../base/ScrollPanel'
import { SpeechCard } from './SpeechCard'
import type { Speech } from '../../types'

interface Props {
  speeches: Speech[]
  streamingContent?: string | null
  streamingSpeaker?: { name: string; color: string } | null
  streamingSeq?: number
}

export const SpeechTimeline: React.FC<Props> = ({
  speeches,
  streamingContent,
  streamingSpeaker,
  streamingSeq = 0,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null)
  const [autoScroll, setAutoScroll] = useState(true)
  const [showBackBtn, setShowBackBtn] = useState(false)

  const handleScroll = useCallback(() => {
    const el = scrollRef.current
    if (!el) return
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 60
    setAutoScroll(atBottom)
    setShowBackBtn(!atBottom)
  }, [])

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [speeches.length, streamingContent, autoScroll])

  const scrollToBottom = () => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
      setAutoScroll(true)
      setShowBackBtn(false)
    }
  }

  const isEmpty = speeches.length === 0 && !streamingContent

  return (
    <div className="speech-timeline">
      <ScrollPanel className="speech-timeline__scroll" onScroll={handleScroll}>
        <div ref={scrollRef}>
          {isEmpty && (
            <div className="speech-timeline__empty">
              <p className="speech-timeline__empty-text">讨论即将开始，嘉宾正在准备中...</p>
            </div>
          )}

          {speeches.map((s) => (
            <SpeechCard key={s.id} speech={s} />
          ))}

          {streamingContent && streamingSpeaker && (
            <SpeechCard
              speech={{
                id: -1,
                discussion_id: 0,
                panelist_id: 0,
                panelist_name: streamingSpeaker.name,
                panelist_color: streamingSpeaker.color,
                content: streamingContent,
                sequence_num: streamingSeq,
                created_at: new Date().toISOString(),
              }}
              isStreaming
            />
          )}
        </div>
      </ScrollPanel>

      {showBackBtn && (
        <button className="speech-timeline__back-btn" onClick={scrollToBottom}>
          回到最新
        </button>
      )}
    </div>
  )
}
