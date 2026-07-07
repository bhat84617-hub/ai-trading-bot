'use client'
import { useEffect, useState, useCallback } from 'react'
import { useStore } from '@/store/useStore'
import { api } from '@/lib/api'
import { BarChart3, TrendingUp, TrendingDown, Activity, DollarSign, RefreshCw, Play, XCircle, AlertTriangle, Loader2, Eye, Zap, Shield } from 'lucide-react'

export default function DashboardPage() {
  const { dashboard, fetchDashboard, loading } = useStore()
  const [signals, setSignals] = useState<any[]>([])
  const [trades, setTrades] = useState<any[]>([])
  const [activeTab, setActiveTab] = useState<'overview' | 'signals' | 'trades' | 'analysis'>('overview')
  const [scanning, setScanning] = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisSymbol, setAnalysisSymbol] = useState('')
  const [analysisResult, setAnalysisResult] = useState<any>(null)

  const loadData = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([api.getSignals(10), api.getTrades(10)])
      setSignals(s)
      setTrades(t)
    } catch (e) { console.error(e) }
  }, [])

  useEffect(() => { fetchDashboard(); loadData() }, [])

  const handleScan = async () => {
    setScanning(true)
    try {
      const res = await api.scan()
      setSignals(res.signals || [])
      await fetchDashboard()
    } catch (e) { console.error(e) }
    setScanning(false)
  }

  const handleApprove = async (id: string, action: 'approve' | 'reject') => {
    try {
      await api.approveSignal(id, action)
      await loadData()
      await fetchDashboard()
    } catch (e) { console.error(e) }
  }

  const handleCloseTrade = async (id: string) => {
    try {
      await api.closeTrade(id)
      await loadData()
      await fetchDashboard()
    } catch (e) { console.error(e) }
  }

  const handleAnalyze = async () => {
    if (!analysisSymbol) return
    setAnalyzing(true)
    try {
      const res = await api.aiAnalyze(analysisSymbol.toUpperCase())
      setAnalysisResult(res)
    } catch (e: any) { console.error(e) }
    setAnalyzing(false)
  }

  const statCards = [
    { label: 'Total PnL', value: `$${dashboard?.total_pnl?.toFixed(2) || '0.00'}`, icon: DollarSign, color: dashboard?.total_pnl >= 0 ? 'text-green-400' : 'text-red-400', bg: dashboard?.total_pnl >= 0 ? 'bg-green-500/10' : 'bg-red-500/10' },
    { label: 'Daily PnL', value: `$${dashboard?.daily_pnl?.toFixed(2) || '0.00'}`, icon: TrendingUp, color: dashboard?.daily_pnl >= 0 ? 'text-green-400' : 'text-red-400', bg: dashboard?.daily_pnl >= 0 ? 'bg-green-500/10' : 'bg-red-500/10' },
    { label: 'Win Rate', value: `${dashboard?.win_rate || 0}%`, icon: Activity, color: 'text-accent', bg: 'bg-accent/10' },
    { label: 'Open Positions', value: dashboard?.open_positions || 0, icon: BarChart3, color: 'text-blue-400', bg: 'bg-blue-500/10' },
    { label: 'Total Trades', value: dashboard?.total_trades || 0, icon: RefreshCw, color: 'text-purple-400', bg: 'bg-purple-500/10' },
    { label: 'Portfolio', value: `$${(dashboard?.portfolio_value || 0).toLocaleString()}`, icon: DollarSign, color: 'text-emerald-400', bg: 'bg-emerald-500/10' },
  ]

  return (
    <div className="max-w-7xl mx-auto px-5 py-6">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {statCards.map((s, i) => (
          <div key={i} className={`card p-4 ${s.bg} animate-slide-up`} style={{ animationDelay: `${i * 50}ms` }}>
            <s.icon size={16} className={s.color} />
            <p className="text-lg font-bold mt-2">{typeof s.value === 'number' ? s.value : s.value}</p>
            <p className="text-xs text-gray-500">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 overflow-x-auto">
        {(['overview', 'signals', 'trades', 'analysis'] as const).map(tab => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={`px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap ${activeTab === tab ? 'bg-accent text-white' : 'bg-white/5 text-gray-400 hover:text-white'}`}>
            {tab === 'overview' ? '📊 Overview' : tab === 'signals' ? '🎯 Signals' : tab === 'trades' ? '📈 Trades' : '🤖 AI Analysis'}
          </button>
        ))}
        <button onClick={handleScan} disabled={scanning} className="px-4 py-2 rounded-xl text-sm font-medium bg-accent/20 text-accent hover:bg-accent/30 transition-all ml-auto flex items-center gap-2 whitespace-nowrap">
          {scanning ? <Loader2 className="animate-spin" size={14} /> : <Zap size={14} />}
          Scan Market
        </button>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <div className="grid lg:grid-cols-2 gap-6">
          <div>
            <h3 className="text-sm font-semibold text-gray-400 mb-3">Recent Signals</h3>
            <div className="space-y-2">
              {(dashboard?.recent_signals || signals).slice(0, 5).map((s: any) => (
                <div key={s.id} className="card p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${s.direction === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>{s.direction === 'long' ? 'L' : 'S'}</span>
                    <div><p className="text-sm font-medium">{s.symbol}</p><p className="text-xs text-gray-500">{s.reason?.slice(0, 50)}...</p></div>
                  </div>
                  <span className={`text-xs font-semibold ${s.confidence_score >= 70 ? 'text-green-400' : s.confidence_score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{s.confidence_score}%</span>
                </div>
              ))}
              {(!dashboard?.recent_signals || dashboard.recent_signals.length === 0) && signals.length === 0 && <p className="text-gray-600 text-sm text-center py-8">No signals yet. Click "Scan Market" to generate.</p>}
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-gray-400 mb-3">Recent Trades</h3>
            <div className="space-y-2">
              {(dashboard?.recent_trades || trades).slice(0, 5).map((t: any) => (
                <div key={t.id} className="card p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${t.direction === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>{t.direction === 'long' ? 'L' : 'S'}</span>
                    <div><p className="text-sm font-medium">{t.symbol}</p><p className="text-xs text-gray-500">{t.status}</p></div>
                  </div>
                  <span className={`text-sm font-bold ${(t.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>${t.pnl?.toFixed(2) || '0.00'}</span>
                </div>
              ))}
              {(!dashboard?.recent_trades || dashboard.recent_trades.length === 0) && trades.length === 0 && <p className="text-gray-600 text-sm text-center py-8">No trades yet.</p>}
            </div>
          </div>
        </div>
      )}

      {/* Signals Tab */}
      {activeTab === 'signals' && (
        <div className="space-y-2">
          {signals.length === 0 ? <p className="text-gray-600 text-sm text-center py-12">No signals generated. Click "Scan Market" to find trading opportunities.</p> : signals.map((s: any) => (
            <div key={s.id} className="card p-5 animate-slide-up">
              <div className="flex items-start justify-between flex-wrap gap-3">
                <div className="flex items-center gap-4">
                  <span className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${s.direction === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>{s.direction === 'long' ? 'LONG' : 'SHORT'}</span>
                  <div>
                    <h4 className="font-semibold">{s.symbol}</h4>
                    <div className="flex gap-4 text-xs text-gray-500 mt-1">
                      <span>Entry: ${s.entry_price}</span>
                      <span>SL: ${s.stop_loss}</span>
                      <span>TP: ${s.take_profit}</span>
                    </div>
                    <p className="text-xs text-gray-500 mt-2">{s.reason}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className={`text-lg font-bold ${s.confidence_score >= 70 ? 'text-green-400' : 'text-yellow-400'}`}>{s.confidence_score}%</p>
                    <p className="text-xs text-gray-500">1:{s.risk_reward_ratio?.toFixed(1)} R:R</p>
                  </div>
                  {s.status === 'pending' && (
                    <div className="flex gap-2">
                      <button onClick={() => handleApprove(s.id, 'approve')} className="px-3 py-1.5 bg-green-500/20 text-green-400 rounded-lg text-xs font-medium hover:bg-green-500/30 transition-colors"><Play size={12} className="inline" /> Trade</button>
                      <button onClick={() => handleApprove(s.id, 'reject')} className="px-3 py-1.5 bg-red-500/20 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/30 transition-colors"><XCircle size={12} className="inline" /> Reject</button>
                    </div>
                  )}
                  <span className={`text-xs px-2 py-1 rounded-full ${s.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' : s.status === 'approved' ? 'bg-blue-500/20 text-blue-400' : s.status === 'rejected' ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>{s.status}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Trades Tab */}
      {activeTab === 'trades' && (
        <div className="space-y-2">
          {trades.length === 0 ? <p className="text-gray-600 text-sm text-center py-12">No trades yet.</p> : trades.map((t: any) => (
            <div key={t.id} className="card p-5 animate-slide-up">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div className="flex items-center gap-4">
                  <span className={`w-10 h-10 rounded-xl flex items-center justify-center font-bold text-sm ${t.direction === 'long' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>{t.direction === 'long' ? 'LONG' : 'SHORT'}</span>
                  <div>
                    <h4 className="font-semibold">{t.symbol}</h4>
                    <div className="flex gap-4 text-xs text-gray-500 mt-1">
                      <span>Entry: ${t.entry_price}</span>
                      {t.exit_price && <span>Exit: ${t.exit_price}</span>}
                      <span>Qty: {t.quantity}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className={`text-lg font-bold ${(t.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>${t.pnl?.toFixed(2) || '0.00'}</p>
                    {t.pnl_percentage && <p className={`text-xs ${(t.pnl_percentage || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>{t.pnl_percentage?.toFixed(1)}%</p>}
                  </div>
                  {t.status === 'open' && <button onClick={() => handleCloseTrade(t.id)} className="px-3 py-1.5 bg-red-500/20 text-red-400 rounded-lg text-xs font-medium hover:bg-red-500/30 transition-colors"><XCircle size={12} className="inline" /> Close</button>}
                  <span className={`text-xs px-2 py-1 rounded-full ${t.status === 'open' ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>{t.status}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* AI Analysis Tab */}
      {activeTab === 'analysis' && (
        <div>
          <div className="card p-6 mb-6">
            <h3 className="font-semibold mb-4 flex items-center gap-2"><Eye size={16} className="text-accent" /> AI Market Analysis</h3>
            <div className="flex gap-3">
              <input value={analysisSymbol} onChange={e => setAnalysisSymbol(e.target.value)} placeholder="Enter symbol (e.g. BTC/USD, TSLA, AAPL)" className="flex-1 px-4 py-2.5 bg-dark-700 border border-white/5 rounded-xl text-sm text-white outline-none focus:border-accent/50 transition-colors" onKeyDown={e => e.key === 'Enter' && handleAnalyze()} />
              <button onClick={handleAnalyze} disabled={analyzing} className="px-6 py-2.5 bg-accent hover:bg-accent/90 text-white rounded-xl text-sm font-medium transition-all flex items-center gap-2">
                {analyzing ? <Loader2 className="animate-spin" size={14} /> : <Zap size={14} />}
                Analyze
              </button>
            </div>
          </div>

          {analysisResult && (
            <div className="card p-6 animate-slide-up">
              <div className="flex items-center justify-between mb-6">
                <h3 className="font-semibold text-lg">{analysisResult.symbol} — AI Analysis</h3>
                <span className={`px-3 py-1 rounded-full text-sm font-bold ${analysisResult.direction === 'long' ? 'bg-green-500/20 text-green-400' : analysisResult.direction === 'short' ? 'bg-red-500/20 text-red-400' : 'bg-gray-500/20 text-gray-400'}`}>{analysisResult.direction.toUpperCase()}</span>
              </div>
              <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                {[
                  { label: 'Entry Price', value: `$${analysisResult.entry_price}` },
                  { label: 'Stop Loss', value: `$${analysisResult.stop_loss}` },
                  { label: 'Take Profit', value: `$${analysisResult.take_profit}` },
                  { label: 'Confidence', value: `${analysisResult.confidence_score}%`, color: analysisResult.confidence_score >= 70 ? 'text-green-400' : 'text-yellow-400' },
                  { label: 'Risk/Reward', value: `1:${analysisResult.risk_reward_ratio?.toFixed(1)}` },
                  { label: 'Risk %', value: `${analysisResult.risk_percentage}%` },
                  { label: 'Sentiment', value: analysisResult.news_sentiment },
                  { label: 'Direction', value: analysisResult.direction.toUpperCase() },
                ].map((item, i) => (
                  <div key={i} className="bg-dark-700 rounded-xl p-3">
                    <p className="text-xs text-gray-500 mb-1">{item.label}</p>
                    <p className={`font-semibold ${item.color || 'text-white'}`}>{item.value}</p>
                  </div>
                ))}
              </div>
              <div className="space-y-4">
                <div>
                  <p className="text-xs text-gray-400 mb-1 font-medium">Reason</p>
                  <p className="text-sm text-gray-300">{analysisResult.reason}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1 font-medium">Trade Explanation</p>
                  <p className="text-sm text-gray-300">{analysisResult.trade_explanation}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-400 mb-1 font-medium">Market Context</p>
                  <p className="text-sm text-gray-300">{analysisResult.market_context}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
