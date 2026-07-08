import { create } from 'zustand'
import { api } from '@/lib/api'

interface User {
  id: string
  email: string
  full_name?: string
  trade_mode: string
  max_risk_per_trade: number
  max_daily_loss: number
  max_drawdown: number
  max_open_positions: number
  min_confidence_score: number
  min_risk_reward: number
}

interface Dashboard {
  total_pnl: number
  daily_pnl: number
  win_rate: number
  open_positions: number
  total_trades: number
  active_signals: number
  portfolio_value: number
  recent_trades: any[]
  recent_signals: any[]
  watchlist: any[]
}

interface AppState {
  user: User | null
  token: string | null
  dashboard: Dashboard | null
  loading: boolean
  setUser: (user: User, token: string) => void
  logout: () => void
  fetchDashboard: () => Promise<void>
  setLoading: (v: boolean) => void
}

export const useStore = create<AppState>((set, get) => ({
  user: null,
  token: null,
  dashboard: null,
  loading: false,

  setUser: (user, token) => {
    localStorage.setItem('auth_token', token)
    set({ user, token })
  },

  logout: () => {
    localStorage.removeItem('auth_token')
    set({ user: null, token: null, dashboard: null })
  },

  fetchDashboard: async () => {
    try {
      set({ loading: true })
      const data = await api.getDashboard()
      set({ dashboard: data })
    } catch (e) {
      console.error('Dashboard fetch failed:', e)
    } finally {
      set({ loading: false })
    }
  },

  setLoading: (v) => set({ loading: v }),
}))
