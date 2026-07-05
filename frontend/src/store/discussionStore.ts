// ============================================================
// AI Panel Studio — 讨论列表状态（Zustand）
// 跨页面共享：首页卡片列表
// 演播厅讨论状态由 StudioPage 本地 useReducer 管理，保证隔离
// ============================================================

import { create } from 'zustand'
import { discussionApi } from '../api/client'
import type { Discussion } from '../types'

interface DiscussionListStore {
  items: Discussion[]
  total: number
  loading: boolean
  error: string | null

  fetchList: (status?: string) => Promise<void>
  createDiscussion: (title: string, topic?: string) => Promise<number>
  deleteDiscussion: (id: number) => Promise<void>
}

export const useDiscussionListStore = create<DiscussionListStore>((set, get) => ({
  items: [],
  total: 0,
  loading: false,
  error: null,

  fetchList: async (status?: string) => {
    set({ loading: true, error: null })
    try {
      const data = await discussionApi.list(status)
      set({ items: data.items, total: data.total, loading: false })
    } catch (e: any) {
      set({ error: e.message || '获取讨论列表失败', loading: false })
    }
  },

  createDiscussion: async (title: string, topic?: string) => {
    const data = await discussionApi.create({ title, topic })
    // 刷新列表
    await get().fetchList()
    return data.id
  },

  deleteDiscussion: async (id: number) => {
    await discussionApi.delete(id)
    await get().fetchList()
  },
}))
