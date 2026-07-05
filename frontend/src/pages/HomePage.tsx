// ============================================================
// HomePage — 首页
// 历史讨论卡片网格 + 新建圆桌按钮
// ============================================================

import React, { useEffect, useState } from 'react'
import { DiscussionCard } from '../components/business/DiscussionCard'
import { NewDiscussionModal } from '../components/business/NewDiscussionModal'
import { useDiscussionListStore } from '../store/discussionStore'

export const HomePage: React.FC = () => {
  const { items, total, loading, fetchList } = useDiscussionListStore()
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    fetchList()
  }, [fetchList])

  return (
    <div className="home-page">
      <header className="home-header">
        <div className="home-header__brand">
          <span className="home-header__logo">🎙️</span>
          <h1 className="home-header__title">AI Panel Studio</h1>
        </div>
        <p className="home-header__subtitle">沉浸式 AI 圆桌演播厅</p>
      </header>

      <div className="home-actions">
        <button className="btn btn-primary btn-lg" onClick={() => setShowModal(true)}>
          ＋ 新建圆桌
        </button>
      </div>

      <section className="home-grid-section">
        {loading && items.length === 0 ? (
          <div className="home-empty">
            <p>加载中…</p>
          </div>
        ) : items.length === 0 ? (
          <div className="home-empty">
            <div className="home-empty__icon">🎬</div>
            <h3>还没有圆桌讨论</h3>
            <p>创建你的第一场 AI 圆桌讨论，邀请虚拟嘉宾展开深度对话</p>
            <button className="btn btn-primary" onClick={() => setShowModal(true)}>
              ＋ 创建第一场讨论
            </button>
          </div>
        ) : (
          <>
            <div className="home-grid-header">
              <h2>历史讨论</h2>
              <span className="home-grid-count">共 {total} 场</span>
            </div>
            <div className="discussion-grid">
              {items.map((d) => (
                <DiscussionCard key={d.id} discussion={d} />
              ))}
            </div>
          </>
        )}
      </section>

      <NewDiscussionModal visible={showModal} onClose={() => setShowModal(false)} />
    </div>
  )
}
