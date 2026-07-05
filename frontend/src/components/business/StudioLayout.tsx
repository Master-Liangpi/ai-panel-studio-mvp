import React, { useState } from 'react'
import { useBreakpoint } from '../base/ResponsiveShell'
import { ScrollPanel } from '../base/ScrollPanel'
import { PanelistWindow } from './PanelistWindow'
import { SpeechTimeline } from './SpeechTimeline'
import { ConsensusList } from './ConsensusList'
import { DivergenceList } from './DivergenceList'
import type { Panelist, Speech, ConsensusPoint, DivergencePoint } from '../../types'

interface Props {
  panelists: Panelist[]
  host: Panelist | null
  experts: Panelist[]
  speeches: Speech[]
  consensus: ConsensusPoint[]
  divergence: DivergencePoint[]
  highlightIds: Set<string>
  streamingContent: string | null
  streamingSpeaker: { name: string; color: string } | null
  streamingSeq: number
  generatingSpeech: boolean
  discussionTitle: string
  onTriggerNext: () => void
}

export const StudioLayout: React.FC<Props> = ({
  panelists,
  host,
  experts,
  speeches,
  consensus,
  divergence,
  highlightIds,
  streamingContent,
  streamingSpeaker,
  streamingSeq,
  generatingSpeech,
  discussionTitle,
  onTriggerNext,
}) => {
  const bp = useBreakpoint()
  const [mobileTab, setMobileTab] = useState<'panelists' | 'speeches' | 'insights'>('speeches')

  const sortedPanelists = [...(host ? [host] : []), ...experts]

  const leftPanel = (
    <div className="studio-panel studio-panel--left">
      <h3 className="studio-panel__title">👥 嘉宾席</h3>
      <ScrollPanel className="studio-panel__scroll">
        {panelists.length === 0 ? (
          <p className="studio-panel__empty">暂无嘉宾，请先生成嘉宾阵容</p>
        ) : (
          sortedPanelists.map((p) => <PanelistWindow key={p.id} panelist={p} />)
        )}
      </ScrollPanel>
    </div>
  )

  const centerPanel = (
    <div className="studio-panel studio-panel--center">
      <div className="studio-panel__title-row">
        <h3 className="studio-panel__title">{discussionTitle}</h3>
      </div>
      <SpeechTimeline
        speeches={speeches}
        streamingContent={streamingContent}
        streamingSpeaker={streamingSpeaker}
        streamingSeq={streamingSeq}
      />
      <div className="studio-panel__actions">
        <button
          className="btn btn-primary"
          disabled={generatingSpeech || panelists.length === 0}
          onClick={onTriggerNext}
        >
          {generatingSpeech ? '嘉宾思考中...' : '🎤 下一轮发言'}
        </button>
      </div>
    </div>
  )

  const rightPanel = (
    <div className="studio-panel studio-panel--right">
      <ConsensusList items={consensus} highlightIds={highlightIds} />
      <div className="insight-divider" />
      <DivergenceList items={divergence} highlightIds={highlightIds} />
    </div>
  )

  if (bp === 'wide') {
    return (
      <div className="studio-layout studio-layout--wide">
        {leftPanel}
        {centerPanel}
        {rightPanel}
      </div>
    )
  }

  if (bp === 'medium') {
    return (
      <div className="studio-layout studio-layout--medium">
        <div className="studio-layout__row-top">
          <div className="studio-layout__left">{leftPanel}</div>
          <div className="studio-layout__center">{centerPanel}</div>
        </div>
        <div className="studio-layout__row-bottom">{rightPanel}</div>
      </div>
    )
  }

  return (
    <div className="studio-layout studio-layout--narrow">
      <div className="mobile-tabs">
        <button
          className={`mobile-tab ${mobileTab === 'panelists' ? 'mobile-tab--active' : ''}`}
          onClick={() => setMobileTab('panelists')}
        >
          👥 嘉宾
        </button>
        <button
          className={`mobile-tab ${mobileTab === 'speeches' ? 'mobile-tab--active' : ''}`}
          onClick={() => setMobileTab('speeches')}
        >
          💬 对话
        </button>
        <button
          className={`mobile-tab ${mobileTab === 'insights' ? 'mobile-tab--active' : ''}`}
          onClick={() => setMobileTab('insights')}
        >
          📌 洞察
        </button>
      </div>
      <div className="mobile-content">
        {mobileTab === 'panelists' && leftPanel}
        {mobileTab === 'speeches' && centerPanel}
        {mobileTab === 'insights' && rightPanel}
      </div>
    </div>
  )
}
