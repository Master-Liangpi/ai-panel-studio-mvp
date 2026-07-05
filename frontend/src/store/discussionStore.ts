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
    await get().fetchList()
    return data.id
  },

  deleteDiscussion: async (id: number) => {
    await discussionApi.delete(id)
    await get().fetchList()
  },
}))
