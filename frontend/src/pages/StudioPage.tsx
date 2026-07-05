// ============================================================
// StudioPage — 演播厅讨论页
// 使用 useReducer 管理单场讨论的全部状态（多场互不干扰）
// 挂载时获取初始数据 + 建立 SSE 连接
// 卸载时关闭 SSE 连接，状态随组件销毁自动隔离
// ============================================================

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

// ---- State & Action ----

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
      // 更新嘉宾状态为 speaking
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
      // 恢复嘉宾状态为 idle
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
      let newConsensus: ConsensusPoint[]
      if (existing >= 0) {
        newConsensus = [...state.consensus]
        newConsensus[existing] = cp
      } else {
        newConsensus = [...state.consensus, cp]
      }
      const newHighlights = new Set(state.highlightIds)
      newHighlights.add(`consensus-${cp.id}`)
      return { ...state, consensus: newConsensus, highlightIds: newHighlights }
    }

    case 'DIVERGENCE_UPDATE': {
      const dp = action.payload
      if (dp.resolved) {
        // 分歧消解：从列表中移除
        return {
          ...state,
          divergence: state.divergence.filter((d) => d.id !== dp.id),
        }
      }
      const existing = state.divergence.findIndex((d) => d.id === dp.id)
      let newDiv: DivergencePoint[]
      if (existing >= 0) {
        newDiv = [...state.divergence]
        newDiv[existing] = dp
      } else {
        newDiv = [...state.divergence, dp]
      }
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

// ---- Component ----

export const StudioPage: React.FC = () => {
  const { discussionId } = useParams<{ discussionId: string }>()
  const navigate = useNavigate()
  const did = Number(discussionId)

  const [state, dispatch] = useReducer(studioReducer, undefined, initState)
  const closeSSERef = useRef<(() => void) | null>(null)

  // ---- 初始化：拉取讨论数据 ----
  useEffect(() => {
    if (!did || isNaN(did)) return

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
    return () => { cancelled = true }
  }, [did, navigate])

  // ---- SSE 连接 ----
  useEffect(() => {
    if (!did || isNaN(did)) return

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
          // 2 秒后清除高亮
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
          dispatch({
            type: 'SET_ERROR',
            payload: data.message || '实时推送异常',
          })
          break

        case 'heartbeat':
          // 心跳对用户透明，仅保持连接
          break
      }
    })

    closeSSERef.current = close

    return () => {
      close()
      closeSSERef.current = null
    }
  }, [did])

  // ---- 触发下一轮发言 ----
  const handleTriggerNext = useCallback(async () => {
    if (!did || state.generatingSpeech) return
    dispatch({ type: 'GENERATING_START' })
    try {
      await speechApi.next(did)
    } catch (e: any) {
      dispatch({ type: 'GENERATING_END' })
      const msg = e.message || '发言触发失败'
      dispatch({ type: 'SET_ERROR', payload: msg })
    }
  }, [did, state.generatingSpeech])

  // ---- 生成总结 ----
  const handleGenerateSummary = useCallback(async () => {
    if (!did) return
    try {
      const res = await summaryApi.generate(did)
      dispatch({ type: 'SET_SUMMARY', payload: res.content })
      // 更新讨论状态
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

  // ---- SSE 重连 ----
  const handleReconnect = useCallback(() => {
    closeSSERef.current?.()
    dispatch({ type: 'SET_SSE_STATUS', payload: 'connecting' })
    const close = createSSEConnection(did, (event, data) => {
      // 复用相同事件处理逻辑
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

  // ---- 退出演播厅 ----
  const handleBack = useCallback(() => {
    navigate('/')
  }, [navigate])

  // ---- 渲染 ----
  return (
    <div className="studio-page">
      <div className="studio-topbar">
        <button className="btn btn-ghost" onClick={handleBack}>
          ← 返回首页
        </button>
        <SseStatusBar status={state.sseStatus} onReconnect={handleReconnect} />
        {state.discussion && state.discussion.status !== 'completed' && state.speeches.length > 0 && (
          <button
            className="btn btn-outline"
            onClick={handleGenerateSummary}
            disabled={state.generatingSpeech}
          >
            📋 结束讨论并生成总结
          </button>
        )}
      </div>

      {state.error && (
        <div className="studio-toast studio-toast--error">
          <span>{state.error}</span>
          <button onClick={() => dispatch({ type: 'SET_ERROR', payload: '' })}>✕</button>
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
        discussionTitle={state.discussion?.title || 'AI 圆桌讨论'}
        onTriggerNext={handleTriggerNext}
      />

      {/* 总结弹窗 */}
      {state.showSummary && state.summary && (
        <div className="summary-overlay" onClick={() => dispatch({ type: 'SET_SUMMARY', payload: '' })}>
          <div className="summary-modal" onClick={(e) => e.stopPropagation()}>
            <div className="summary-modal__header">
              <h2>📋 讨论总结</h2>
              <button
                className="modal-close"
                onClick={() => dispatch({ type: 'SET_SUMMARY', payload: '' })}
              >
                ✕
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
