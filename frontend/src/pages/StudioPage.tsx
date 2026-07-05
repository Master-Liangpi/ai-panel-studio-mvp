import React, { useReducer, useEffect, useCallback, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { SseStatusBar } from '../components/base/SseStatusBar'
import { StudioLayout } from '../components/business/StudioLayout'
import {
  discussionApi,
  panelistApi,
  speechApi,
  consensusApi,
  divergenceApi,
  summaryApi,
  createSSEConnection,
} from '../api/client'
import type {
  Discussion,
  Panelist,
  PanelistStatus,
  Speech,
  ConsensusPoint,
  DivergencePoint,
} from '../types'
import { sanitizeDisplayText } from '../utils/text'

interface StudioState {
  discussion: Discussion | null
  panelists: Panelist[]
  host: Panelist | null
  experts: Panelist[]
  speeches: Speech[]
  consensus: ConsensusPoint[]
  divergence: DivergencePoint[]
  sseStatus: 'connecting' | 'connected' | 'disconnected'
  generatingSpeech: boolean
  streamingContent: string | null
  streamingSpeaker: { name: string; color: string } | null
  streamingSeq: number
  highlightIds: Set<string>
  error: string | null
  summary: string | null
  showSummary: boolean
}

type Action =
  | { type: 'SET_DISCUSSION'; payload: Discussion }
  | { type: 'SET_PANELISTS'; payload: { host: Panelist | null; experts: Panelist[]; items: Panelist[] } }
  | { type: 'SET_SPEECHES'; payload: Speech[] }
  | { type: 'SET_CONSENSUS'; payload: ConsensusPoint[] }
  | { type: 'SET_DIVERGENCE'; payload: DivergencePoint[] }
  | { type: 'SET_SSE_STATUS'; payload: 'connecting' | 'connected' | 'disconnected' }
  | { type: 'SPEECH_CHUNK'; payload: { sequence_num: number; panelist_id: number; delta: string } }
  | { type: 'SPEECH_COMPLETE'; payload: Speech }
  | { type: 'CONSENSUS_UPDATE'; payload: ConsensusPoint }
  | { type: 'DIVERGENCE_UPDATE'; payload: DivergencePoint }
  | { type: 'GENERATING_START' }
  | { type: 'GENERATING_END' }
  | { type: 'SET_ERROR'; payload: string }
  | { type: 'SET_SUMMARY'; payload: string }
  | { type: 'CLEAR_HIGHLIGHT'; payload: string }

function initState(): StudioState {
  return {
    discussion: null,
    panelists: [],
    host: null,
    experts: [],
    speeches: [],
    consensus: [],
    divergence: [],
    sseStatus: 'connecting',
    generatingSpeech: false,
    streamingContent: null,
    streamingSpeaker: null,
    streamingSeq: 0,
    highlightIds: new Set(),
    error: null,
    summary: null,
    showSummary: false,
  }
}

function studioReducer(state: StudioState, action: Action): StudioState {
  switch (action.type) {
    case 'SET_DISCUSSION':
      return { ...state, discussion: action.payload }
    case 'SET_PANELISTS': {
      const items = action.payload.items.map((p) => ({
        ...p,
        ui_status: 'idle' as PanelistStatus,
      }))
      const host = items.find((p) => p.role === 'host') || null
      if (host) host.ui_status = 'idle'
      const experts = items.filter((p) => p.role === 'expert')
      return { ...state, panelists: items, host, experts }
    }
    case 'SET_SPEECHES':
      return { ...state, speeches: action.payload }
    case 'SET_CONSENSUS':
      return { ...state, consensus: action.payload }
    case 'SET_DIVERGENCE':
      return { ...state, divergence: action.payload }
    case 'SET_SSE_STATUS':
      return { ...state, sseStatus: action.payload }
    case 'SPEECH_CHUNK': {
      const { panelist_id, delta } = action.payload
      const wasFirstChunk = !state.streamingContent
      const newContent = (state.streamingContent || '') + delta
      const updatedPanelists = state.panelists.map((p) =>
        p.id === panelist_id ? { ...p, ui_status: 'speaking' as PanelistStatus } : p
      )
      return {
        ...state,
        streamingContent: newContent,
        streamingSeq: action.payload.sequence_num,
        streamingSpeaker: wasFirstChunk
          ? (() => {
              const sp = state.panelists.find((p) => p.id === panelist_id)
              return sp ? { name: sp.name, color: sp.color } : null
            })()
          : state.streamingSpeaker,
        panelists: updatedPanelists,
      }
    }
    case 'SPEECH_COMPLETE': {
      const speech = action.payload
      const resetPanelists = state.panelists.map((p) =>
        p.id === speech.panelist_id ? { ...p, ui_status: 'idle' as PanelistStatus } : p
      )
      return {
        ...state,
        speeches: [...state.speeches, speech],
        panelists: resetPanelists,
        streamingContent: null,
        streamingSpeaker: null,
        streamingSeq: 0,
      }
    }
    case 'CONSENSUS_UPDATE': {
      const cp = action.payload
      const existing = state.consensus.findIndex((c) => c.id === cp.id)
      const newConsensus =
        existing >= 0
          ? state.consensus.map((c, index) => (index === existing ? cp : c))
          : [...state.consensus, cp]
      const newHighlights = new Set(state.highlightIds)
      newHighlights.add(`consensus-${cp.id}`)
      return { ...state, consensus: newConsensus, highlightIds: newHighlights }
    }
    case 'DIVERGENCE_UPDATE': {
      const dp = action.payload
      if (dp.resolved) {
        return {
          ...state,
          divergence: state.divergence.filter((d) => d.id !== dp.id),
        }
      }
      const existing = state.divergence.findIndex((d) => d.id === dp.id)
      const newDiv =
        existing >= 0
          ? state.divergence.map((d, index) => (index === existing ? dp : d))
          : [...state.divergence, dp]
      const newHighlights = new Set(state.highlightIds)
      newHighlights.add(`divergence-${dp.id}`)
      return { ...state, divergence: newDiv, highlightIds: newHighlights }
    }
    case 'GENERATING_START':
      return { ...state, generatingSpeech: true, error: null }
    case 'GENERATING_END':
      return { ...state, generatingSpeech: false }
    case 'SET_ERROR':
      return { ...state, error: action.payload, generatingSpeech: false }
    case 'SET_SUMMARY':
      return { ...state, summary: action.payload, showSummary: true }
    case 'CLEAR_HIGHLIGHT': {
      const newHighlights = new Set(state.highlightIds)
      newHighlights.delete(action.payload)
      return { ...state, highlightIds: newHighlights }
    }
    default:
      return state
  }
}

export const StudioPage: React.FC = () => {
  const { discussionId } = useParams<{ discussionId: string }>()
  const navigate = useNavigate()
  const did = Number(discussionId)

  const [state, dispatch] = useReducer(studioReducer, undefined, initState)
  const closeSSERef = useRef<(() => void) | null>(null)

  useEffect(() => {
    if (!did || Number.isNaN(did)) return

    let cancelled = false

    async function init() {
      try {
        const [disc, panelistsRes, speechesRes, consensusRes, divergenceRes] = await Promise.all([
          discussionApi.get(did),
          panelistApi.list(did),
          speechApi.list(did),
          consensusApi.list(did),
          divergenceApi.list(did),
        ])
        if (cancelled) return
        dispatch({ type: 'SET_DISCUSSION', payload: disc })
        dispatch({
          type: 'SET_PANELISTS',
          payload: {
            host: panelistsRes.host,
            experts: panelistsRes.experts,
            items: panelistsRes.items,
          },
        })
        dispatch({ type: 'SET_SPEECHES', payload: speechesRes.items })
        dispatch({ type: 'SET_CONSENSUS', payload: consensusRes.items })
        dispatch({ type: 'SET_DIVERGENCE', payload: divergenceRes.items })
      } catch (e: any) {
        if (!cancelled) {
          dispatch({ type: 'SET_ERROR', payload: e.message || '数据加载失败' })
          if (e.status === 404) {
            navigate('/', { replace: true })
          }
        }
      }
    }

    init()
    return () => {
      cancelled = true
    }
  }, [did, navigate])

  useEffect(() => {
    if (!did || Number.isNaN(did)) return

    dispatch({ type: 'SET_SSE_STATUS', payload: 'connecting' })

    const close = createSSEConnection(did, (event, data) => {
      switch (event) {
        case '__connected__':
          dispatch({ type: 'SET_SSE_STATUS', payload: 'connected' })
          break
        case '__disconnected__':
          dispatch({ type: 'SET_SSE_STATUS', payload: 'disconnected' })
          break
        case 'speech.chunk':
          dispatch({ type: 'SPEECH_CHUNK', payload: data })
          break
        case 'speech.complete':
          dispatch({ type: 'SPEECH_COMPLETE', payload: data })
          dispatch({ type: 'GENERATING_END' })
          break
        case 'consensus.update':
          dispatch({ type: 'CONSENSUS_UPDATE', payload: data })
          setTimeout(() => {
            dispatch({ type: 'CLEAR_HIGHLIGHT', payload: `consensus-${data.id}` })
          }, 2200)
          break
        case 'divergence.update':
          dispatch({ type: 'DIVERGENCE_UPDATE', payload: data })
          if (!data.resolved) {
            setTimeout(() => {
              dispatch({ type: 'CLEAR_HIGHLIGHT', payload: `divergence-${data.id}` })
            }, 2200)
          }
          break
        case 'error':
          dispatch({ type: 'GENERATING_END' })
          dispatch({ type: 'SET_ERROR', payload: data.message || '实时推送异常' })
          break
        case 'heartbeat':
          break
      }
    })

    closeSSERef.current = close
    return () => {
      close()
      closeSSERef.current = null
    }
  }, [did])

  const handleTriggerNext = useCallback(async () => {
    if (!did || state.generatingSpeech) return
    dispatch({ type: 'GENERATING_START' })
    try {
      await speechApi.next(did)
    } catch (e: any) {
      dispatch({ type: 'GENERATING_END' })
      dispatch({ type: 'SET_ERROR', payload: e.message || '发言触发失败' })
    }
  }, [did, state.generatingSpeech])

  const handleGenerateSummary = useCallback(async () => {
    if (!did) return
    try {
      const res = await summaryApi.generate(did)
      dispatch({ type: 'SET_SUMMARY', payload: res.content })
      if (state.discussion) {
        dispatch({
          type: 'SET_DISCUSSION',
          payload: { ...state.discussion, status: 'completed' },
        })
      }
    } catch (e: any) {
      dispatch({ type: 'SET_ERROR', payload: e.message || '总结生成失败' })
    }
  }, [did, state.discussion])

  const handleReconnect = useCallback(() => {
    closeSSERef.current?.()
    dispatch({ type: 'SET_SSE_STATUS', payload: 'connecting' })
    const close = createSSEConnection(did, (event, data) => {
      switch (event) {
        case '__connected__':
          dispatch({ type: 'SET_SSE_STATUS', payload: 'connected' })
          break
        case '__disconnected__':
          dispatch({ type: 'SET_SSE_STATUS', payload: 'disconnected' })
          break
        case 'speech.chunk':
          dispatch({ type: 'SPEECH_CHUNK', payload: data })
          break
        case 'speech.complete':
          dispatch({ type: 'SPEECH_COMPLETE', payload: data })
          dispatch({ type: 'GENERATING_END' })
          break
        case 'consensus.update':
          dispatch({ type: 'CONSENSUS_UPDATE', payload: data })
          setTimeout(() => dispatch({ type: 'CLEAR_HIGHLIGHT', payload: `consensus-${data.id}` }), 2200)
          break
        case 'divergence.update':
          dispatch({ type: 'DIVERGENCE_UPDATE', payload: data })
          if (!data.resolved) {
            setTimeout(() => dispatch({ type: 'CLEAR_HIGHLIGHT', payload: `divergence-${data.id}` }), 2200)
          }
          break
        case 'error':
          dispatch({ type: 'GENERATING_END' })
          dispatch({ type: 'SET_ERROR', payload: data.message || '实时推送异常' })
          break
      }
    })
    closeSSERef.current = close
  }, [did])

  const safeDiscussionTitle = sanitizeDisplayText(
    state.discussion?.title,
    state.discussion ? `圆桌讨论 #${state.discussion.id}` : 'AI 圆桌讨论',
  )

  return (
    <div className="studio-page">
      <div className="studio-topbar">
        <button className="btn btn-ghost" onClick={() => navigate('/')}>
          返回首页
        </button>
        <SseStatusBar status={state.sseStatus} onReconnect={handleReconnect} />
        {state.discussion && state.discussion.status !== 'completed' && state.speeches.length > 0 && (
          <button
            className="btn btn-outline"
            onClick={handleGenerateSummary}
            disabled={state.generatingSpeech}
          >
            结束讨论并生成总结
          </button>
        )}
      </div>

      {state.error && (
        <div className="studio-toast studio-toast--error">
          <span>{state.error}</span>
          <button onClick={() => dispatch({ type: 'SET_ERROR', payload: '' })}>x</button>
        </div>
      )}

      <StudioLayout
        panelists={state.panelists}
        host={state.host}
        experts={state.experts}
        speeches={state.speeches}
        consensus={state.consensus}
        divergence={state.divergence}
        highlightIds={state.highlightIds}
        streamingContent={state.streamingContent}
        streamingSpeaker={state.streamingSpeaker}
        streamingSeq={state.streamingSeq}
        generatingSpeech={state.generatingSpeech}
        discussionTitle={safeDiscussionTitle}
        onTriggerNext={handleTriggerNext}
      />

      {state.showSummary && state.summary && (
        <div className="summary-overlay" onClick={() => dispatch({ type: 'SET_SUMMARY', payload: '' })}>
          <div className="summary-modal" onClick={(e) => e.stopPropagation()}>
            <div className="summary-modal__header">
              <h2>讨论总结</h2>
              <button
                className="modal-close"
                onClick={() => dispatch({ type: 'SET_SUMMARY', payload: '' })}
              >
                x
              </button>
            </div>
            <div
              className="summary-modal__content"
              dangerouslySetInnerHTML={{
                __html: (state.summary || '')
                  .replace(/^## (.+)$/gm, '<h2>$1</h2>')
                  .replace(/^### (.+)$/gm, '<h3>$1</h3>')
                  .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
                  .replace(/^- (.+)$/gm, '<li>$1</li>')
                  .replace(/\n{2,}/g, '<br/>')
                  .replace(/\n/g, '<br/>'),
              }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
