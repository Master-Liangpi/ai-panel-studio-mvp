// ============================================================
// AI Panel Studio — API 客户端
// REST 请求 + SSE EventSource 管理
// ============================================================

const API_BASE = '/api/v1'

// ---- REST 请求 ----

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err = new Error(body.message || `请求失败: ${res.status}`) as Error & {
      code: string
      status: number
    }
    err.code = body.code || 'UNKNOWN'
    err.status = res.status
    throw err
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// ---- 讨论 ----

export const discussionApi = {
  list: (status?: string, page = 1, pageSize = 20) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (status) params.set('status', status)
    return request<any>(`/discussions?${params}`)
  },
  get: (id: number) => request<any>(`/discussions/${id}`),
  create: (data: { title: string; topic?: string }) =>
    request<any>('/discussions', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Record<string, unknown>) =>
    request<any>(`/discussions/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: number) =>
    request<void>(`/discussions/${id}`, { method: 'DELETE' }),
}

// ---- 嘉宾 ----

export const panelistApi = {
  list: (discussionId: number) => request<any>(`/discussions/${discussionId}/panelists`),
  generate: (discussionId: number, data: { count: number; topic_override?: string }) =>
    request<any>(`/discussions/${discussionId}/panelists/generate`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  add: (discussionId: number, data: Record<string, unknown>) =>
    request<any>(`/discussions/${discussionId}/panelists`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  update: (discussionId: number, panelistId: number, data: Record<string, unknown>) =>
    request<any>(`/discussions/${discussionId}/panelists/${panelistId}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
  delete: (discussionId: number, panelistId: number) =>
    request<void>(`/discussions/${discussionId}/panelists/${panelistId}`, { method: 'DELETE' }),
}

// ---- 发言 ----

export const speechApi = {
  list: (discussionId: number, afterSequence?: number, page = 1, pageSize = 50) => {
    const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
    if (afterSequence !== undefined) params.set('after_sequence', String(afterSequence))
    return request<any>(`/discussions/${discussionId}/speeches?${params}`)
  },
  next: (discussionId: number, promptHint?: string) =>
    request<any>(`/discussions/${discussionId}/speeches/next`, {
      method: 'POST',
      body: JSON.stringify(promptHint ? { prompt_hint: promptHint } : {}),
    }),
}

// ---- 共识/分歧 ----

export const consensusApi = {
  list: (discussionId: number) => request<any>(`/discussions/${discussionId}/consensus`),
}

export const divergenceApi = {
  list: (discussionId: number) => request<any>(`/discussions/${discussionId}/divergence`),
}

// ---- 总结 ----

export const summaryApi = {
  get: (discussionId: number) => request<any>(`/discussions/${discussionId}/summary`),
  generate: (discussionId: number) =>
    request<any>(`/discussions/${discussionId}/summary`, { method: 'POST' }),
}

// ---- SSE ----

export type SSECallback = (event: string, data: any) => void

export function createSSEConnection(discussionId: number, onEvent: SSECallback): () => void {
  const url = `${API_BASE}/discussions/${discussionId}/stream`

  // 断线重连：记录最后收到的 sequence_num
  let lastSequence = 0
  let eventSource: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let stopped = false

  function connect() {
    if (stopped) return
    const connectUrl = lastSequence > 0 ? `${url}?after_sequence=${lastSequence}` : url
    eventSource = new EventSource(connectUrl)

    eventSource.onopen = () => {
      onEvent('__connected__', null)
    }

    eventSource.onerror = () => {
      onEvent('__disconnected__', null)
      eventSource?.close()
      // 自动重连
      if (!stopped) {
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    // 注册所有业务事件
    const events = [
      'speech.chunk',
      'speech.complete',
      'consensus.update',
      'divergence.update',
      'error',
      'heartbeat',
    ]
    for (const evt of events) {
      eventSource.addEventListener(evt, (e: MessageEvent) => {
        const data = JSON.parse(e.data)
        // 记录最后 sequence（用于断线重连补偿）
        if (evt === 'speech.complete' && data.sequence_num) {
          lastSequence = data.sequence_num
        }
        onEvent(evt, data)
      })
    }
  }

  connect()

  // 返回清理函数
  return () => {
    stopped = true
    if (reconnectTimer) clearTimeout(reconnectTimer)
    eventSource?.close()
  }
}
