// ============================================================
// AI Panel Studio — 前端类型定义
// 对齐后端 OpenAPI 接口契约（api-contract.yaml）
// ============================================================

// ---- 讨论 ----
export interface Discussion {
  id: number
  title: string
  topic: string
  status: 'active' | 'paused' | 'completed'
  panelist_count: number
  speech_count: number
  created_at: string
  updated_at: string
}

export interface DiscussionCreateRequest {
  title: string
  topic?: string
}

export interface DiscussionUpdateRequest {
  title?: string
  topic?: string
  status?: 'active' | 'paused' | 'completed'
}

export interface DiscussionListResponse {
  items: Discussion[]
  total: number
}

// ---- 嘉宾 ----
export type PanelistRole = 'host' | 'expert'
export type PanelistStatus = 'idle' | 'preparing' | 'speaking' | 'offline'

export interface Panelist {
  id: number
  discussion_id: number
  name: string
  title: string
  stance: string
  color: string
  role: PanelistRole
  avatar_url: string | null
  created_at: string
  // 前端运行时状态（不从后端返回，由 SSE 驱动）
  ui_status: PanelistStatus
}

export interface PanelistGenerateRequest {
  count: number
  topic_override?: string
}

export interface PanelistCreateRequest {
  name: string
  title?: string
  stance?: string
  color?: string
  role: PanelistRole
  avatar_url?: string
}

export interface PanelistListResponse {
  items: Panelist[]
  host: Panelist | null
  experts: Panelist[]
}

// ---- 发言 ----
export interface Speech {
  id: number
  discussion_id: number
  panelist_id: number
  panelist_name: string
  panelist_color: string
  content: string
  sequence_num: number
  created_at: string
}

export interface SpeechNextRequest {
  prompt_hint?: string
}

export interface SpeechNextResponse {
  accepted: boolean
  message: string
  estimated_seconds: number
}

export interface SpeechListResponse {
  items: Speech[]
  total: number
}

// ---- 共识 ----
export interface ConsensusPoint {
  id: number
  discussion_id: number
  topic: string
  content: string
  latest_speech_id: number | null
  created_at: string
  updated_at: string
}

export interface ConsensusListResponse {
  items: ConsensusPoint[]
  total: number
}

// ---- 分歧 ----
export interface DivergencePoint {
  id: number
  discussion_id: number
  topic: string
  content: string
  sides: string
  latest_speech_id: number | null
  created_at: string
  updated_at: string
  resolved?: boolean  // 前端标记：分歧已被消解
}

export interface DivergenceListResponse {
  items: DivergencePoint[]
  total: number
}

// ---- 总结 ----
export interface SummaryResponse {
  discussion_id: number
  content: string
  generated_at: string
}

// ---- SSE 事件 Payload ----
export interface SSEChunkPayload {
  sequence_num: number
  panelist_id: number
  delta: string
}

export interface SSEErrorPayload {
  code: string
  message: string
}

// ---- 通用 ----
export interface ErrorResponse {
  code: string
  message: string
  detail?: string
}

// ---- SSE 事件类型 ----
export type SSEEventType =
  | 'speech.chunk'
  | 'speech.complete'
  | 'consensus.update'
  | 'divergence.update'
  | 'error'
  | 'heartbeat'

// ---- 讨论状态（前端聚合） ----
export interface DiscussionState {
  discussion: Discussion | null
  panelists: Panelist[]
  host: Panelist | null
  experts: Panelist[]
  speeches: Speech[]
  consensus: ConsensusPoint[]
  divergence: DivergencePoint[]
  sseStatus: 'connecting' | 'connected' | 'disconnected'
  generatingSpeech: boolean
  streamingChunk: {
    sequence_num: number
    panelist_id: number
    content: string
  } | null
  highlightIds: Set<string>  // 需要高亮动画的条目 ID
}
