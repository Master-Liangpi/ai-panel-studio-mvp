// ============================================================
// ResponsiveShell — 响应式外层壳
// 根据视口宽度切换三档布局：
//   ≥1440px 宽屏三栏
//   768–1439px 双栏堆叠
//   <768px 单栏 Tab 切换
// 页面 body 永远 overflow: hidden（无整页滚动）
// ============================================================

import React, { useState, useEffect, createContext, useContext } from 'react'

// ---- 断点常量 ----
export const BREAKPOINTS = {
  WIDE: 1440,
  MEDIUM: 768,
} as const

export type Breakpoint = 'wide' | 'medium' | 'narrow'

export const BreakpointContext = createContext<Breakpoint>('wide')

export const useBreakpoint = () => useContext(BreakpointContext)

// ---- 组件 ----

interface Props {
  children: React.ReactNode
}

export const ResponsiveShell: React.FC<Props> = ({ children }) => {
  const [bp, setBp] = useState<Breakpoint>(() => getBreakpoint())

  useEffect(() => {
    const onResize = () => setBp(getBreakpoint())
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  return (
    <BreakpointContext.Provider value={bp}>
      <div className={`responsive-shell bp-${bp}`}>{children}</div>
    </BreakpointContext.Provider>
  )
}

function getBreakpoint(): Breakpoint {
  const w = window.innerWidth
  if (w >= BREAKPOINTS.WIDE) return 'wide'
  if (w >= BREAKPOINTS.MEDIUM) return 'medium'
  return 'narrow'
}
