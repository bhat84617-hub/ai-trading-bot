const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://ai-trading-bot-backend-9eyn.onrender.com'

async function request(path: string, options?: RequestInit) {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: 'Request failed' }))
    throw new Error(err.message || err.detail || 'Request failed')
  }
  return res.json()
}

export const api = {
  login: (email: string, password: string) =>
    request('/api/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  signup: (email: string, password: string, fullName?: string) =>
    request('/api/auth/signup', { method: 'POST', body: JSON.stringify({ email, password, full_name: fullName }) }),
  getMe: () => request('/api/me'),
  updateSettings: (data: any) => request('/api/me/settings', { method: 'PUT', body: JSON.stringify(data) }),
  getWatchlist: () => request('/api/watchlist'),
  addToWatchlist: (symbol: string, timeframe = '1h') =>
    request('/api/watchlist', { method: 'POST', body: JSON.stringify({ symbol, timeframe }) }),
  removeFromWatchlist: (id: string) => request(`/api/watchlist/${id}`, { method: 'DELETE' }),
  scan: () => request('/api/scan', { method: 'POST' }),
  getSignals: (limit = 20, status?: string) =>
    request(`/api/signals?limit=${limit}${status ? `&status=${status}` : ''}`),
  approveSignal: (id: string, action: 'approve' | 'reject') =>
    request(`/api/signals/${id}/approve`, { method: 'POST', body: JSON.stringify({ action }) }),
  getTrades: (limit = 20, status?: string) =>
    request(`/api/trades?limit=${limit}${status ? `&status=${status}` : ''}`),
  closeTrade: (id: string, exitPrice?: number) =>
    request(`/api/trades/${id}/close`, { method: 'POST', body: JSON.stringify({ exit_price: exitPrice }) }),
  getPortfolio: () => request('/api/portfolio'),
  getPnL: () => request('/api/pnl'),
  getDashboard: () => request('/api/dashboard'),
  aiAnalyze: (symbol: string, timeframe = '1h') =>
    request('/api/ai/analyze', { method: 'POST', body: JSON.stringify({ symbol, timeframe }) }),
  switchBroker: (broker: string) =>
    request('/api/broker/switch', { method: 'POST', body: JSON.stringify({ broker }) }),
  getBrokers: () => request('/api/broker/list'),
}
